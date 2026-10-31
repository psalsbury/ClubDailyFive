<?php
// Fan tables and private leagues for the Daily Five.
// Shared helpers only: this file does nothing when requested directly.
declare(strict_types=1);
if (realpath((string)($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) { http_response_code(404); exit; }
date_default_timezone_set('Europe/London');

define('LG_DB', getenv('CDF_LEAGUES_DB') ?: '/var/lib/clubdailyfive/leagues.sqlite');
const LG_QUIZ_DB = '/var/lib/clubdailyfive/clubquiz.sqlite';
const LG_CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

function lg_db(): PDO {
    static $pdo = null;
    if ($pdo) return $pdo;
    $pdo = new PDO('sqlite:' . LG_DB, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
    $pdo->exec('PRAGMA busy_timeout=4000; PRAGMA foreign_keys=ON;');
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS score_counts(play_date TEXT NOT NULL, club_slug TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(play_date, club_slug, score)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, public_id TEXT NOT NULL UNIQUE, token_hash TEXT NOT NULL UNIQUE, name TEXT NOT NULL, name_key TEXT NOT NULL, home_club TEXT NOT NULL, hidden INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(home_club, name_key));
CREATE TABLE IF NOT EXISTS rounds(player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE, play_date TEXT NOT NULL, club_slug TEXT NOT NULL, score INTEGER NOT NULL, marks TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(player_id, play_date));
CREATE INDEX IF NOT EXISTS rounds_club_day ON rounds(club_slug, play_date);
CREATE TABLE IF NOT EXISTS leagues(id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS league_members(league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE, player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE, joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(league_id, player_id)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS members_player ON league_members(player_id);
CREATE TABLE IF NOT EXISTS rate_limits(bucket TEXT NOT NULL, day TEXT NOT NULL, total INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(bucket, day)) WITHOUT ROWID;');
    return $pdo;
}

function lg_today(): string { return date('Y-m-d'); }
function lg_week_start(?string $day = null): string { return (new DateTimeImmutable($day ?? lg_today()))->modify('monday this week')->format('Y-m-d'); }
function lg_h(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8'); }

function lg_quiz_db(): PDO {
    static $q = null;
    if (!$q) { $q = new PDO('sqlite:' . LG_QUIZ_DB, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]); $q->exec('PRAGMA busy_timeout=4000'); }
    return $q;
}

/** @return array<string,array{slug:string,name:string,accent:string,logo_path:?string,league:string,id:int}> */
function lg_clubs(): array {
    static $clubs = null;
    if ($clubs === null) {
        $clubs = [];
        foreach (lg_quiz_db()->query('SELECT id,slug,name,accent,logo_path,league FROM clubs WHERE active=1 ORDER BY name') as $c) $clubs[$c['slug']] = $c;
    }
    return $clubs;
}

/** Correct answer indexes for the round a club is serving today (same rule as index.php). */
function lg_today_answers(string $slug): ?array {
    $club = lg_clubs()[$slug] ?? null;
    if (!$club) return null;
    $q = lg_quiz_db();
    $d = $q->prepare('SELECT quiz_date FROM daily_questions WHERE club_id=? AND quiz_date<=? GROUP BY quiz_date HAVING COUNT(*)=5 ORDER BY quiz_date DESC LIMIT 1');
    $d->execute([(int)$club['id'], lg_today()]);
    $date = $d->fetchColumn();
    if (!$date) return null;
    $s = $q->prepare('SELECT q.correct_index FROM daily_questions dq JOIN questions q ON q.id=dq.question_id WHERE dq.club_id=? AND dq.quiz_date=? ORDER BY dq.position');
    $s->execute([(int)$club['id'], $date]);
    $a = array_map('intval', $s->fetchAll(PDO::FETCH_COLUMN));
    return count($a) === 5 ? $a : null;
}

function lg_secret(): string {
    $db = lg_db();
    $v = $db->query("SELECT v FROM meta WHERE k='secret'")->fetchColumn();
    if (!$v) { $v = bin2hex(random_bytes(32)); $db->prepare("INSERT OR IGNORE INTO meta(k,v) VALUES('secret',?)")->execute([$v]); $v = $db->query("SELECT v FROM meta WHERE k='secret'")->fetchColumn(); }
    return (string)$v;
}

/** Simple per-IP daily limits; the IP itself is never stored. */
function lg_rate_ok(string $action, int $limit): bool {
    $db = lg_db();
    $bucket = $action . ':' . substr(hash_hmac('sha256', (string)($_SERVER['REMOTE_ADDR'] ?? ''), lg_secret()), 0, 20);
    $day = lg_today();
    $db->prepare('INSERT INTO rate_limits(bucket,day,total) VALUES(?,?,1) ON CONFLICT(bucket,day) DO UPDATE SET total=total+1')->execute([$bucket, $day]);
    $s = $db->prepare('SELECT total FROM rate_limits WHERE bucket=? AND day=?'); $s->execute([$bucket, $day]);
    if (random_int(1, 50) === 1) $db->prepare('DELETE FROM rate_limits WHERE day<?')->execute([date('Y-m-d', strtotime('-2 days'))]);
    return (int)$s->fetchColumn() <= $limit;
}

function lg_token_hash(string $token): string { return hash('sha256', $token); }

function lg_player(?string $token): ?array {
    if (!$token || !preg_match('/^[a-f0-9]{48}$/', $token)) return null;
    $s = lg_db()->prepare('SELECT * FROM players WHERE token_hash=?');
    $s->execute([lg_token_hash($token)]);
    return $s->fetch() ?: null;
}

const LG_BLOCKED = ['fuck','fuk','shit','cunt','nigg','nigga','fag','wank','twat','whore','rape','nazi','hitler','paki','retard','spaz','bitch','dick','cock','pussy','prick','bastard','slut','coon','kike','tranny','dyke','bellend','nonce','paedo','pedo','munich','hillsborough','heysel','ibrox'];

function lg_is_blocked(string $text): bool {
    $flat = strtolower(preg_replace('/[^\p{L}\p{N}]/u', '', strtr($text, ['0' => 'o', '1' => 'i', '3' => 'e', '4' => 'a', '5' => 's', '$' => 's', '@' => 'a'])) ?? '');
    foreach (LG_BLOCKED as $w) if (str_contains($flat, $w) && !str_contains($flat, 'scunthorpe')) return true;
    return (bool)preg_match('/^(admin|clubdailyfive|moderator|official)/', $flat);
}

/** @return array{0:?string,1:string} [error, cleaned name] */
function lg_clean_name(string $raw): array {
    $name = trim(preg_replace('/\s+/u', ' ', $raw) ?? '');
    if (!preg_match('/^[\p{L}\p{N} ._\'’-]{2,20}$/u', $name)) return ['Use 2–20 letters, numbers or spaces.', $name];
    if (!preg_match('/[\p{L}\p{N}]/u', $name)) return ['Use some letters or numbers.', $name];
    if (lg_is_blocked($name)) return ['Please choose a different name.', $name];
    return [null, $name];
}
function lg_name_key(string $name): string { return strtolower(preg_replace('/[^\p{L}\p{N}]/u', '', $name) ?? $name); }

function lg_random_code(int $len, string $chars): string { $o = ''; for ($i = 0; $i < $len; $i++) $o .= $chars[random_int(0, strlen($chars) - 1)]; return $o; }

/** Today's anonymous score spread for a club. */
function lg_distribution(string $slug, ?string $day = null): array {
    $s = lg_db()->prepare('SELECT score,total FROM score_counts WHERE play_date=? AND club_slug=?');
    $s->execute([$day ?? lg_today(), $slug]);
    $dist = array_fill(0, 6, 0);
    foreach ($s as $r) $dist[(int)$r['score']] = (int)$r['total'];
    $played = array_sum($dist);
    $sum = 0; foreach ($dist as $k => $v) $sum += $k * $v;
    return ['played' => $played, 'average' => $played ? round($sum / $played, 1) : null, 'dist' => $dist];
}

/** Share of players who scored strictly lower, plus half the ties (the usual percentile rule). */
function lg_beat_pct(array $dist, int $score): ?int {
    $played = array_sum($dist);
    if ($played < 2) return null;
    $lower = 0; for ($i = 0; $i < $score; $i++) $lower += $dist[$i];
    $others = $played - 1;
    $tiesOthers = max(0, $dist[$score] - 1);
    return (int)round(100 * ($lower + $tiesOthers / 2) / $others);
}

/** Rank rows (already sorted) with shared positions for equal keys. */
function lg_rank(array $rows, callable $key): array {
    $pos = 0; $prev = null; $i = 0;
    foreach ($rows as &$r) { $i++; $k = $key($r); if ($k !== $prev) { $pos = $i; $prev = $k; } $r['rank'] = $pos; }
    unset($r);
    $counts = array_count_values(array_column($rows, 'rank'));
    foreach ($rows as &$r) $r['joint'] = ($counts[$r['rank']] ?? 0) > 1;
    unset($r);
    return $rows;
}

function lg_ordinal(int $n): string {
    $s = ['th', 'st', 'nd', 'rd']; $v = $n % 100;
    return $n . ($s[($v - 20) % 10] ?? $s[$v] ?? $s[0]);
}

/**
 * Table for a set of players. $where filters players (p alias); period is today|week|all.
 * @return list<array{public_id:string,name:string,home_club:string,points:int,played:int,today:?int,marks:?string,rank:int,joint:bool}>
 */
function lg_table(string $period, string $where, array $params, int $limit = 200): array {
    $today = lg_today();
    if ($period === 'today') {
        $sql = "SELECT p.public_id,p.name,p.home_club,r.score AS points,1 AS played,r.score AS today,r.marks FROM players p JOIN rounds r ON r.player_id=p.id AND r.play_date=? WHERE p.hidden=0 AND $where ORDER BY points DESC, r.created_at ASC LIMIT $limit";
        $args = array_merge([$today], $params);
    } else {
        $from = $period === 'week' ? lg_week_start() : '0000-00-00';
        $sql = "SELECT p.public_id,p.name,p.home_club,COALESCE(SUM(r.score),0) AS points,COUNT(r.play_date) AS played,
                MAX(CASE WHEN r.play_date=? THEN r.score END) AS today, MAX(CASE WHEN r.play_date=? THEN r.marks END) AS marks
                FROM players p LEFT JOIN rounds r ON r.player_id=p.id AND r.play_date>=? AND r.play_date<=?
                WHERE p.hidden=0 AND $where GROUP BY p.id HAVING played>0 ORDER BY points DESC, played ASC, p.name COLLATE NOCASE LIMIT $limit";
        $args = array_merge([$today, $today, $from, $today], $params);
    }
    $s = lg_db()->prepare($sql); $s->execute($args);
    $rows = $s->fetchAll();
    foreach ($rows as &$r) { $r['points'] = (int)$r['points']; $r['played'] = (int)$r['played']; $r['today'] = $r['today'] === null ? null : (int)$r['today']; }
    unset($r);
    return lg_rank($rows, fn($r) => $period === 'week' || $period === 'all' ? $r['points'] . ':' . $r['played'] : (string)$r['points']);
}

/** League members (including those who haven't played in a period) for a league page. */
function lg_league_members(int $leagueId): array {
    $s = lg_db()->prepare('SELECT p.public_id,p.name,p.home_club FROM league_members m JOIN players p ON p.id=m.player_id WHERE m.league_id=? AND p.hidden=0 ORDER BY p.name COLLATE NOCASE');
    $s->execute([$leagueId]);
    return $s->fetchAll();
}

function lg_league_by_code(string $code): ?array {
    $code = strtoupper(preg_replace('/[^A-Za-z0-9]/', '', $code) ?? '');
    if (strlen($code) !== 6) return null;
    $s = lg_db()->prepare('SELECT l.*, (SELECT COUNT(*) FROM league_members m WHERE m.league_id=l.id) AS members FROM leagues l WHERE code=?');
    $s->execute([$code]);
    return $s->fetch() ?: null;
}

/** Consecutive days with a counted round, ending today or yesterday. */
function lg_streak(int $playerId): int {
    $s = lg_db()->prepare('SELECT play_date FROM rounds WHERE player_id=? ORDER BY play_date DESC LIMIT 400');
    $s->execute([$playerId]);
    $days = $s->fetchAll(PDO::FETCH_COLUMN);
    $expect = new DateTimeImmutable(lg_today());
    if ($days && $days[0] !== $expect->format('Y-m-d')) $expect = $expect->modify('-1 day');
    $n = 0;
    foreach ($days as $d) { if ($d !== $expect->format('Y-m-d')) break; $n++; $expect = $expect->modify('-1 day'); }
    return $n;
}

/* ------------------------------------------------------------------ club v club */

const LG_CLUB_TABLE_MIN = 3; // rounds a club needs in a period before it gets a position

/** Each club's main rival among the clubs on the site (one-way where the rivalry is lopsided). */
const LG_RIVALS = [
    'arsenal' => 'tottenham-hotspur', 'tottenham-hotspur' => 'arsenal', 'chelsea' => 'tottenham-hotspur',
    'liverpool' => 'everton', 'everton' => 'liverpool',
    'manchester-united' => 'manchester-city', 'manchester-city' => 'manchester-united', 'leeds-united' => 'manchester-united',
    'newcastle-united' => 'sunderland', 'sunderland' => 'newcastle-united', 'middlesbrough' => 'sunderland',
    'nottingham-forest' => 'derby-county', 'derby-county' => 'nottingham-forest',
    'aston-villa' => 'birmingham-city', 'birmingham-city' => 'aston-villa',
    'west-bromwich-albion' => 'wolverhampton-wanderers', 'wolverhampton-wanderers' => 'west-bromwich-albion',
    'cardiff-city' => 'swansea-city', 'swansea-city' => 'cardiff-city', 'bristol-city' => 'cardiff-city',
    'portsmouth' => 'southampton', 'southampton' => 'portsmouth', 'bournemouth' => 'southampton',
    'blackburn-rovers' => 'burnley', 'burnley' => 'blackburn-rovers', 'preston-north-end' => 'blackburn-rovers',
    'norwich-city' => 'ipswich-town', 'ipswich-town' => 'norwich-city',
    'millwall' => 'west-ham-united', 'west-ham-united' => 'millwall', 'charlton-athletic' => 'millwall',
    'crystal-palace' => 'brighton', 'brighton' => 'crystal-palace',
    'fulham' => 'chelsea', 'brentford' => 'queens-park-rangers', 'queens-park-rangers' => 'brentford',
];

/**
 * Clubs ranked by their players' average Daily Five score for a period (today|week|all),
 * from the anonymous score counts. Clubs with fewer than LG_CLUB_TABLE_MIN rounds are unranked.
 * @return array{ranked:list<array>, unranked:list<array>, by_slug:array<string,array>}
 */
function lg_club_table(string $period): array {
    static $cache = [];
    if (isset($cache[$period])) return $cache[$period];
    $today = lg_today();
    $from = $period === 'today' ? $today : ($period === 'week' ? lg_week_start() : '0000-00-00');
    $s = lg_db()->prepare('SELECT club_slug, SUM(total) AS played, SUM(score*total) AS points FROM score_counts WHERE play_date>=? AND play_date<=? GROUP BY club_slug');
    $s->execute([$from, $today]);
    $stats = [];
    foreach ($s as $r) $stats[$r['club_slug']] = ['played' => (int)$r['played'], 'points' => (int)$r['points']];
    $ranked = $unranked = [];
    foreach (lg_clubs() as $slug => $c) {
        $st = $stats[$slug] ?? ['played' => 0, 'points' => 0];
        $row = ['slug' => $slug, 'name' => $c['name'], 'league' => $c['league'], 'logo' => $c['logo_path'], 'played' => $st['played'],
                'average' => $st['played'] ? round($st['points'] / $st['played'], 2) : null];
        if ($st['played'] >= LG_CLUB_TABLE_MIN) $ranked[] = $row; else $unranked[] = $row;
    }
    usort($ranked, fn($a, $b) => [$b['average'], $b['played'], $a['name']] <=> [$a['average'], $a['played'], $b['name']]);
    $ranked = lg_rank($ranked, fn($r) => number_format((float)$r['average'], 2));
    usort($unranked, fn($a, $b) => [$b['played'], $a['name']] <=> [$a['played'], $b['name']]);
    $by = [];
    foreach ($ranked as $r) $by[$r['slug']] = $r;
    foreach ($unranked as $r) $by[$r['slug']] = $r + ['rank' => null, 'joint' => false];
    return $cache[$period] = ['ranked' => $ranked, 'unranked' => $unranked, 'by_slug' => $by];
}

/** Today's club-table position and rival comparison for one club (for the result panel). */
function lg_club_vs(string $slug): array {
    $t = lg_club_table('today');
    $me = $t['by_slug'][$slug] ?? null;
    $out = ['club_table' => null, 'rival' => null];
    if ($me && $me['rank']) $out['club_table'] = ['rank' => $me['rank'], 'joint' => $me['joint'], 'of' => count($t['ranked']), 'label' => ($me['joint'] ? 'joint ' : '') . lg_ordinal((int)$me['rank']), 'average' => $me['average']];
    $rival = LG_RIVALS[$slug] ?? null;
    if ($rival && $me && ($r = $t['by_slug'][$rival] ?? null) && $me['played'] >= 2 && $r['played'] >= 2) {
        $out['rival'] = ['slug' => $rival, 'name' => $r['name'], 'average' => $r['average'], 'played' => $r['played'], 'my_average' => $me['average'], 'my_played' => $me['played']];
    }
    return $out;
}

/** Shared page chrome for the league pages. */
function lg_page_head(string $title, string $description, string $accent = '#ffcc33'): void { ?>
<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title><?= lg_h($title) ?></title><meta name="description" content="<?= lg_h($description) ?>"><meta name="robots" content="noindex,follow"><meta name="theme-color" content="#07101e"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="manifest" href="/manifest.webmanifest">
<meta property="og:title" content="<?= lg_h($title) ?>"><meta property="og:description" content="<?= lg_h($description) ?>"><meta property="og:image" content="https://clubdailyfive.com/assets/games/og-games.jpg"><meta property="og:type" content="website">
<style>:root{--ink:#f7f8fc;--muted:#a9b2c4;--line:#273650;--bg:#07101e}*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 80% -10%,color-mix(in srgb,var(--accent) 22%,transparent),transparent 36rem),var(--bg);min-height:100vh}.wrap{width:min(760px,calc(100% - 28px));margin:auto}.top{padding:22px 0}.brand img{display:block;width:min(450px,72vw);height:auto}.eyebrow{color:var(--accent);text-transform:uppercase;letter-spacing:.14em;font-weight:800;font-size:.75rem}a{color:var(--accent)}.foot{color:#778399;font-size:.76rem;padding:30px 0 36px;text-align:center}.foot-links{display:flex;justify-content:center;flex-wrap:wrap;gap:8px 16px;margin-bottom:10px}.foot-links a{color:#a9b2c4;text-decoration:none}@media(max-width:600px){.top{padding:14px 0}}</style><link rel="stylesheet" href="/assets/leagues.css?v=2"><link rel="stylesheet" href="/assets/site-header.css?v=2"><style>:root{--accent:<?= lg_h(preg_match('/^#[0-9a-f]{6}$/i', $accent) ? $accent : '#ffcc33') ?>}</style></head>
<body><main class="wrap"><header class="top site-header"><a class="brand" href="/" aria-label="ClubDailyFive.com home"><img src="/assets/clubdailyfive-logo.svg?v=20261005" alt="ClubDailyFive.com" width="450" height="60"></a></header>
<?php }

function lg_page_foot(): void { ?>
<footer class="foot"><nav class="foot-links" aria-label="Site information"><a href="/daily-football-quiz">Football quiz</a><a href="/player-wordle-game">Player Wordle</a><a href="/leagues">Leagues</a><a href="/club-table">Club table</a><a href="/about">About</a><a href="/privacy">Privacy Policy</a><a href="/contact">Contact</a></nav><span>Independent supporter quiz. Not affiliated with or endorsed by the Premier League or any club.</span></footer></main>
<script src="/assets/leagues.js?v=3"></script></body></html>
<?php }

/** Render a table body for a period. */
function lg_render_table(array $rows, string $period, bool $showClub, string $empty): void {
    $clubs = lg_clubs();
    if (!$rows) { echo '<p class="lg-empty">' . lg_h($empty) . '</p>'; return; }
    echo '<ol class="lg-table">';
    foreach ($rows as $r) {
        $club = $clubs[$r['home_club']] ?? null;
        echo '<li data-player="' . lg_h($r['public_id']) . '"><span class="lg-pos">' . ($r['joint'] ? '=' : '') . (int)$r['rank'] . '</span>';
        echo '<span class="lg-name">' . lg_h($r['name']);
        if ($showClub && $club) echo '<small>' . lg_h($club['name']) . '</small>';
        echo '</span>';
        if ($period === 'today') {
            $marks = (string)($r['marks'] ?? '');
            echo '<span class="lg-marks" aria-hidden="true">' . lg_h(strtr($marks, ['1' => '🟩', '0' => '⬛'])) . '</span><span class="lg-pts">' . (int)$r['points'] . '<small>/5</small></span>';
        } else {
            echo '<span class="lg-played">' . (int)$r['played'] . ' ' . ($r['played'] === 1 ? 'round' : 'rounds') . '</span><span class="lg-pts">' . (int)$r['points'] . '<small>pts</small></span>';
        }
        echo '</li>';
    }
    echo '</ol>';
}
