<?php
// Daily Five reminders: Web Push using only PHP's openssl (RFC 8291 aes128gcm + RFC 8292 VAPID).
// Adapted from salsbury.uk's api/_lib/push.php. Helpers only: does nothing when requested directly.
declare(strict_types=1);
if (realpath((string)($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) { http_response_code(404); exit; }
require_once __DIR__ . '/leagues-lib.php';

const PUSH_CONFIG = '/etc/clubdailyfive/push-vapid.json';
/** Reminder times (UK). */
const PUSH_SLOTS = ['morning' => ['08:00', '8am'], 'lunch' => ['12:30', '12:30pm'], 'evening' => ['18:00', '6pm']];

function push_config(): array {
    static $c = null;
    if ($c === null) {
        $c = is_readable(PUSH_CONFIG) ? (json_decode((string)file_get_contents(PUSH_CONFIG), true) ?: []) : [];
        $c += ['vapid_public' => '', 'vapid_private' => '', 'subject' => 'mailto:admin@clubdailyfive.com'];
    }
    return $c;
}
function push_ready(): bool { return push_config()['vapid_public'] !== '' && push_config()['vapid_private'] !== ''; }

function push_db(): PDO {
    $db = lg_db();
    static $made = false;
    if (!$made) {
        $db->exec('CREATE TABLE IF NOT EXISTS push_subs(endpoint TEXT PRIMARY KEY, p256dh TEXT NOT NULL, auth TEXT NOT NULL, club_slug TEXT NOT NULL,
            slot TEXT NOT NULL DEFAULT \'morning\', last_played TEXT, streak INTEGER NOT NULL DEFAULT 0, last_sent TEXT, last_ok INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)');
        $made = true;
    }
    return $db;
}

function b64u(string $s): string { return rtrim(strtr(base64_encode($s), '+/', '-_'), '='); }
function b64u_dec(string $s): string { return (string)base64_decode(strtr($s, '-_', '+/') . str_repeat('=', (4 - strlen($s) % 4) % 4), true); }

// Only ever post to the browsers' own push services (Chrome/Android, Apple, Firefox, Edge).
function push_known_host(string $host): bool {
    return (bool)preg_match('/^(fcm\.googleapis\.com|android\.googleapis\.com|web\.push\.apple\.com|[a-z0-9-]+\.push\.services\.mozilla\.com|[a-z0-9-]+\.notify\.windows\.com)$/', $host);
}

function push_pub_pem(string $point): string {
    $der = hex2bin('3059301306072a8648ce3d020106082a8648ce3d030107034200') . $point;
    return "-----BEGIN PUBLIC KEY-----\n" . chunk_split(base64_encode($der), 64, "\n") . "-----END PUBLIC KEY-----\n";
}

function push_vapid_key() {
    static $key = null;
    if ($key === null) {
        $c = push_config();
        $der = hex2bin('30770201010420') . b64u_dec($c['vapid_private'])
            . hex2bin('a00a06082a8648ce3d030107a144034200') . b64u_dec($c['vapid_public']);
        $key = openssl_pkey_get_private("-----BEGIN EC PRIVATE KEY-----\n" . chunk_split(base64_encode($der), 64, "\n") . "-----END EC PRIVATE KEY-----\n");
        if (!$key) throw new RuntimeException('VAPID key is not valid.');
    }
    return $key;
}

function push_vapid_jwt(string $endpoint): string {
    $u = parse_url($endpoint);
    $head = b64u(json_encode(['typ' => 'JWT', 'alg' => 'ES256']));
    $claims = b64u(json_encode(['aud' => $u['scheme'] . '://' . $u['host'], 'exp' => time() + 12 * 3600, 'sub' => push_config()['subject']]));
    openssl_sign("$head.$claims", $der, push_vapid_key(), OPENSSL_ALGO_SHA256);
    $o = 3 + (ord($der[1]) & 0x80 ? 1 : 0);
    $rl = ord($der[$o]); $r = substr($der, $o + 1, $rl);
    $o += 1 + $rl + 1;
    $sl = ord($der[$o]); $s = substr($der, $o + 1, $sl);
    $fix = fn($n) => str_pad(ltrim($n, "\0"), 32, "\0", STR_PAD_LEFT);
    return "$head.$claims." . b64u($fix($r) . $fix($s));
}

function push_encrypt(string $payload, string $uaPublic, string $authSecret): string {
    $eph = openssl_pkey_new(['curve_name' => 'prime256v1', 'private_key_type' => OPENSSL_KEYTYPE_EC]);
    $d = openssl_pkey_get_details($eph)['ec'];
    $asPublic = "\x04" . str_pad($d['x'], 32, "\0", STR_PAD_LEFT) . str_pad($d['y'], 32, "\0", STR_PAD_LEFT);
    $shared = openssl_pkey_derive(openssl_pkey_get_public(push_pub_pem($uaPublic)), $eph, 32);
    if ($shared === false) throw new RuntimeException('ECDH failed.');
    $prkKey = hash_hmac('sha256', $shared, $authSecret, true);
    $ikm = hash_hmac('sha256', "WebPush: info\0" . $uaPublic . $asPublic . "\x01", $prkKey, true);
    $salt = random_bytes(16);
    $prk = hash_hmac('sha256', $ikm, $salt, true);
    $cek = substr(hash_hmac('sha256', "Content-Encoding: aes128gcm\0\x01", $prk, true), 0, 16);
    $nonce = substr(hash_hmac('sha256', "Content-Encoding: nonce\0\x01", $prk, true), 0, 12);
    $ct = openssl_encrypt($payload . "\x02", 'aes-128-gcm', $cek, OPENSSL_RAW_DATA, $nonce, $tag);
    return $salt . pack('N', 4096) . chr(65) . $asPublic . $ct . $tag;
}

/** Sends one message. Returns the HTTP status (0 if the push service couldn't be reached). */
function push_send_one(array $sub, array $msg, string $topic): int {
    $body = push_encrypt(json_encode($msg, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), b64u_dec($sub['p256dh']), b64u_dec($sub['auth']));
    $ctx = stream_context_create(['http' => [
        'method' => 'POST', 'timeout' => 8, 'ignore_errors' => true,
        'header' => implode("\r\n", [
            'Content-Type: application/octet-stream', 'Content-Encoding: aes128gcm', 'Content-Length: ' . strlen($body),
            'TTL: ' . 6 * 3600, // a reminder is useless the next day
            'Urgency: normal', 'Topic: ' . $topic,
            'Authorization: vapid t=' . push_vapid_jwt($sub['endpoint']) . ', k=' . push_config()['vapid_public'],
        ]),
        'content' => $body,
    ]]);
    $res = @file_get_contents($sub['endpoint'], false, $ctx);
    $status = 0;
    foreach ($http_response_header ?? [] as $h) if (preg_match('#^HTTP/\S+ (\d{3})#', $h, $m)) $status = (int)$m[1];
    if ($status < 200 || $status >= 300) error_log("ClubDailyFive push: $status from " . parse_url($sub['endpoint'], PHP_URL_HOST) . ' ' . substr((string)$res, 0, 200));
    return $status;
}

/** The reminder for one subscriber today. */
function push_message(array $sub): array {
    $club = lg_clubs()[$sub['club_slug']] ?? null;
    $name = $club['name'] ?? 'your club';
    $today = lg_today();
    $yesterday = date('Y-m-d', strtotime('-1 day'));
    $title = "⚽ Today’s $name Daily Five is ready";
    $body = 'Five new questions. Can you get 5/5?';
    if ($club) {
        // Lead with the matchday question when there is one.
        $s = lg_quiz_db()->prepare("SELECT q.question_text FROM daily_questions d JOIN questions q ON q.id=d.question_id WHERE d.club_id=? AND d.quiz_date=? AND q.semantic_key LIKE 'matchday|%' LIMIT 1");
        $s->execute([(int)$club['id'], $today]);
        if ($s->fetchColumn()) $body = 'Today opens with a matchday question on yesterday’s game.';
    }
    if (($sub['last_played'] ?? '') === $yesterday && (int)$sub['streak'] >= 2) {
        $body .= ' Keep your ' . (int)$sub['streak'] . '-day streak going 🔥';
    }
    return ['title' => $title, 'body' => $body, 'url' => '/daily-five/' . $sub['club_slug'] . '?from=reminder', 'tag' => 'daily-five-' . $today];
}
