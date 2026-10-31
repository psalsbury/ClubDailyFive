<?php
// JSON API for fan tables and private leagues.
declare(strict_types=1);
require __DIR__ . '/leagues-lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex');

function out(array $data, int $status = 200): never { http_response_code($status); echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); exit; }
function fail(string $error, int $status = 422): never { out(['ok' => false, 'error' => $error], $status); }

$isBot = (bool)preg_match('/bot|crawl|spider|slurp|Google-|facebookexternalhit|headless/i', (string)($_SERVER['HTTP_USER_AGENT'] ?? ''));

try {
    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $club = (string)($_GET['club'] ?? '');
        if (!isset(lg_clubs()[$club])) fail('Unknown club');
        out(['ok' => true] + lg_stats_payload($club, null, null));
    }
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') fail('Method not allowed', 405);
    if (!preg_match('#^https://(www\.)?clubdailyfive\.com$#i', (string)($_SERVER['HTTP_ORIGIN'] ?? ''))) fail('Forbidden', 403);
    if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 4096) fail('Too large', 413);
    if ($isBot) out(['ok' => true]);
    $d = json_decode((string)file_get_contents('php://input'), true);
    if (!is_array($d)) fail('Bad request');
    $action = (string)($d['action'] ?? '');
    $player = lg_player(isset($d['token']) ? (string)$d['token'] : null);
    $db = lg_db();

    switch ($action) {
        case 'result': {
            // Count a finished round. Choices are re-marked on the server against today's round.
            $club = (string)($d['club'] ?? '');
            if (!isset(lg_clubs()[$club])) fail('Unknown club');
            if (($d['play_date'] ?? '') !== lg_today()) fail('This round has finished');
            $choices = $d['choices'] ?? null;
            $answers = lg_today_answers($club);
            if (!$answers || !is_array($choices) || count($choices) !== 5) fail('Bad round');
            $marks = '';
            foreach (array_values($choices) as $i => $c) { if (!is_int($c) || $c < 0 || $c > 5) fail('Bad round'); $marks .= $c === $answers[$i] ? '1' : '0'; }
            $score = substr_count($marks, '1');
            if (($d['count'] ?? false) === true) {
                $db->prepare('INSERT INTO score_counts(play_date,club_slug,score,total) VALUES(?,?,?,1) ON CONFLICT(play_date,club_slug,score) DO UPDATE SET total=total+1')->execute([lg_today(), $club, $score]);
            }
            $counted = false;
            if ($player && $player['home_club'] === $club) {
                $ins = $db->prepare('INSERT OR IGNORE INTO rounds(player_id,play_date,club_slug,score,marks) VALUES(?,?,?,?,?)');
                $ins->execute([(int)$player['id'], lg_today(), $club, $score, $marks]);
                $counted = true;
            }
            out(['ok' => true, 'score' => $score, 'marks' => $marks, 'counted' => $counted] + lg_stats_payload($club, $player, $score));
        }
        case 'register': {
            if ($player) fail('You already have a name on this device');
            [$err, $name] = lg_clean_name((string)($d['name'] ?? ''));
            if ($err) fail($err);
            $home = (string)($d['home_club'] ?? '');
            if (!isset(lg_clubs()[$home])) fail('Choose your club');
            if (!lg_rate_ok('register', 12)) fail('Too many new names from this connection today. Try again tomorrow.', 429);
            $token = bin2hex(random_bytes(24));
            try {
                $db->prepare('INSERT INTO players(public_id,token_hash,name,name_key,home_club) VALUES(?,?,?,?,?)')
                   ->execute([lg_random_code(10, 'abcdefghijkmnpqrstuvwxyz23456789'), lg_token_hash($token), $name, lg_name_key($name), $home]);
            } catch (PDOException $e) {
                if (str_contains($e->getMessage(), 'UNIQUE')) fail('Another ' . lg_clubs()[$home]['name'] . ' fan already uses that name.');
                throw $e;
            }
            $player = lg_player($token);
            out(['ok' => true, 'token' => $token] + lg_me_payload($player));
        }
        case 'me': {
            if (!$player) fail('Not found', 404);
            out(['ok' => true] + lg_me_payload($player));
        }
        case 'update': {
            if (!$player) fail('Not found', 404);
            [$err, $name] = lg_clean_name((string)($d['name'] ?? $player['name']));
            if ($err) fail($err);
            $home = (string)($d['home_club'] ?? $player['home_club']);
            if (!isset(lg_clubs()[$home])) fail('Choose your club');
            if ($home !== $player['home_club']) {
                // Changing club starts a fresh record so old scores don't move between club tables.
                if (!lg_rate_ok('switch', 3)) fail('You can only change club a few times a day.', 429);
            }
            try {
                $db->beginTransaction();
                $db->prepare('UPDATE players SET name=?,name_key=?,home_club=? WHERE id=?')->execute([$name, lg_name_key($name), $home, (int)$player['id']]);
                if ($home !== $player['home_club']) $db->prepare('DELETE FROM rounds WHERE player_id=?')->execute([(int)$player['id']]);
                $db->commit();
            } catch (PDOException $e) {
                if ($db->inTransaction()) $db->rollBack();
                if (str_contains($e->getMessage(), 'UNIQUE')) fail('Another ' . lg_clubs()[$home]['name'] . ' fan already uses that name.');
                throw $e;
            }
            out(['ok' => true] + lg_me_payload(lg_player((string)$d['token'])));
        }
        case 'create_league': {
            if (!$player) fail('Pick a name first', 401);
            $name = trim(preg_replace('/\s+/u', ' ', (string)($d['name'] ?? '')) ?? '');
            if (!preg_match('/^[\p{L}\p{N} ._\'’&!?()-]{3,32}$/u', $name)) fail('League names need 3–32 letters or numbers.');
            if (lg_is_blocked($name)) fail('Please choose a different league name.');
            $mine = $db->prepare('SELECT COUNT(*) FROM league_members WHERE player_id=?'); $mine->execute([(int)$player['id']]);
            if ((int)$mine->fetchColumn() >= 20) fail('You can be in up to 20 leagues.');
            if (!lg_rate_ok('league', 8)) fail('Too many new leagues from this connection today.', 429);
            for ($i = 0; $i < 8; $i++) {
                $code = lg_random_code(6, LG_CODE_CHARS);
                try { $db->prepare('INSERT INTO leagues(code,name,owner_id) VALUES(?,?,?)')->execute([$code, $name, (int)$player['id']]); break; }
                catch (PDOException $e) { if (!str_contains($e->getMessage(), 'UNIQUE') || $i === 7) throw $e; }
            }
            $id = (int)$db->lastInsertId();
            $db->prepare('INSERT OR IGNORE INTO league_members(league_id,player_id) VALUES(?,?)')->execute([$id, (int)$player['id']]);
            out(['ok' => true, 'code' => $code, 'url' => 'https://clubdailyfive.com/league/' . $code] + lg_me_payload($player));
        }
        case 'join_league': {
            if (!$player) fail('Pick a name first', 401);
            $league = lg_league_by_code((string)($d['code'] ?? ''));
            if (!$league) fail('No league with that code.', 404);
            if ((int)$league['members'] >= 300) fail('That league is full.');
            $mine = $db->prepare('SELECT COUNT(*) FROM league_members WHERE player_id=?'); $mine->execute([(int)$player['id']]);
            if ((int)$mine->fetchColumn() >= 20) fail('You can be in up to 20 leagues.');
            $db->prepare('INSERT OR IGNORE INTO league_members(league_id,player_id) VALUES(?,?)')->execute([(int)$league['id'], (int)$player['id']]);
            out(['ok' => true, 'code' => $league['code']] + lg_me_payload($player));
        }
        case 'leave_league': {
            if (!$player) fail('Not found', 404);
            $league = lg_league_by_code((string)($d['code'] ?? ''));
            if (!$league) fail('No league with that code.', 404);
            $db->prepare('DELETE FROM league_members WHERE league_id=? AND player_id=?')->execute([(int)$league['id'], (int)$player['id']]);
            out(['ok' => true] + lg_me_payload($player));
        }
        case 'delete_me': {
            if (!$player) fail('Not found', 404);
            $db->prepare('DELETE FROM leagues WHERE owner_id=? AND id NOT IN (SELECT league_id FROM league_members WHERE player_id<>?)')->execute([(int)$player['id'], (int)$player['id']]);
            $db->prepare('UPDATE leagues SET owner_id=(SELECT player_id FROM league_members m WHERE m.league_id=leagues.id AND m.player_id<>? ORDER BY joined_at LIMIT 1) WHERE owner_id=?')->execute([(int)$player['id'], (int)$player['id']]);
            $db->prepare('DELETE FROM players WHERE id=?')->execute([(int)$player['id']]);
            out(['ok' => true]);
        }
    }
    fail('Unknown action');
} catch (Throwable $e) {
    error_log('ClubDailyFive leagues API: ' . $e->getMessage());
    fail('Something went wrong. Please try again.', 500);
}

function lg_me_payload(array $p): array {
    $s = lg_db()->prepare('SELECT l.code,l.name,(SELECT COUNT(*) FROM league_members x WHERE x.league_id=l.id) AS members FROM league_members m JOIN leagues l ON l.id=m.league_id WHERE m.player_id=? ORDER BY m.joined_at');
    $s->execute([(int)$p['id']]);
    $t = lg_db()->prepare('SELECT score FROM rounds WHERE player_id=? AND play_date=?'); $t->execute([(int)$p['id'], lg_today()]);
    $today = $t->fetchColumn();
    return ['me' => ['id' => $p['public_id'], 'name' => $p['name'], 'home_club' => $p['home_club'], 'home_club_name' => lg_clubs()[$p['home_club']]['name'] ?? '', 'today' => $today === false ? null : (int)$today, 'streak' => lg_streak((int)$p['id']), 'leagues' => array_map(fn($l) => ['code' => $l['code'], 'name' => $l['name'], 'members' => (int)$l['members']], $s->fetchAll())]];
}

function lg_stats_payload(string $club, ?array $player, ?int $score): array {
    $dist = lg_distribution($club);
    $table = lg_table('today', 'p.home_club=?', [$club], 500);
    $out = lg_club_vs($club) + ['played' => $dist['played'], 'average' => $dist['average'], 'dist' => $dist['dist'], 'beat' => $score === null ? null : lg_beat_pct($dist['dist'], $score), 'named' => count($table), 'top' => array_map(fn($r) => ['name' => $r['name'], 'score' => $r['points'], 'rank' => $r['rank'], 'joint' => $r['joint'], 'id' => $r['public_id']], array_slice($table, 0, 5))];
    if ($player) {
        foreach ($table as $r) if ($r['public_id'] === $player['public_id']) { $out['my_rank'] = ['rank' => $r['rank'], 'joint' => $r['joint'], 'of' => count($table), 'label' => ($r['joint'] ? 'joint ' : '') . lg_ordinal((int)$r['rank'])]; break; }
        $out += lg_me_payload($player);
    }
    return $out;
}
