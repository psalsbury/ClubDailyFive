<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');

const DB_PATH = '/var/lib/clubdailyfive/clubquiz.sqlite';

function db(): PDO {
    $pdo = new PDO('sqlite:' . DB_PATH, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=4000;');
    return $pdo;
}

function h(string $value): string { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }

$pdo = db();
$clubs = $pdo->query("SELECT slug,name,accent,logo_path,league FROM clubs WHERE active=1 ORDER BY name")->fetchAll(PDO::FETCH_ASSOC);
$wordleDb = new PDO('sqlite:/var/lib/clubdailyfive/player-wordle/game.sqlite3', null, null, [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$wordleReady=$wordleDb->query("SELECT c.slug FROM clubs c JOIN daily_game d ON d.club_id=c.id WHERE d.game_date='".date('Y-m-d')."'")->fetchAll(PDO::FETCH_COLUMN);
$wordleReady=array_fill_keys($wordleReady,true);
function wordleSlug(string $slug): string { return ['coventry-city'=>'coventry','hull-city'=>'hull','ipswich-town'=>'ipswich','leeds-united'=>'leeds','manchester-city'=>'man-city','manchester-united'=>'man-utd','newcastle-united'=>'newcastle','tottenham-hotspur'=>'tottenham'][$slug]??$slug; }
$selectedGame = in_array((string)($_GET['game'] ?? ''), ['daily','wordle'], true) ? (string)$_GET['game'] : '';
$slug = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($_GET['club'] ?? '')));
$club = null;
if ($slug !== '') {
    $stmt = $pdo->prepare('SELECT id,slug,name,accent,logo_path FROM clubs WHERE slug=? AND active=1');
    $stmt->execute([$slug]);
    $club = $stmt->fetch(PDO::FETCH_ASSOC) ?: null;
}

if ($slug !== '' && !$club) { http_response_code(404); }
$questions = [];
$quizDate = (new DateTimeImmutable('now', new DateTimeZone('Europe/London')))->format('Y-m-d');
$sourceQuizDate = $quizDate;
if ($club) {
    // Always serve the newest complete round. A failed or partial midnight
    // publication must never leave a club with an empty quiz.
    $dateStmt = $pdo->prepare('SELECT quiz_date
        FROM daily_questions
        WHERE club_id=? AND quiz_date<=?
        GROUP BY quiz_date
        HAVING COUNT(*)=5
        ORDER BY quiz_date DESC LIMIT 1');
    $dateStmt->execute([(int)$club['id'], $quizDate]);
    $sourceQuizDate = (string)($dateStmt->fetchColumn() ?: $quizDate);

    $stmt = $pdo->prepare('SELECT q.id,q.question_text,q.options_json,q.correct_index,q.explanation,q.source_url,q.source_label,dq.position
        FROM daily_questions dq JOIN questions q ON q.id=dq.question_id
        WHERE dq.club_id=? AND dq.quiz_date=? ORDER BY dq.position');
    $stmt->execute([(int)$club['id'], $sourceQuizDate]);
    $questions = $stmt->fetchAll(PDO::FETCH_ASSOC);
}
$dateLabel = (new DateTimeImmutable($quizDate))->format('j F Y');
$canonicalUrl = 'https://clubdailyfive.com/';
if ($club) {
    $canonicalUrl .= 'daily-five/' . rawurlencode((string)$club['slug']);
}
$pageTitle = $club
    ? $club['name'] . ' Football Quiz – Daily Five | ClubDailyFive'
    : 'Daily Football Quiz & Player Wordle | ClubDailyFive';
$pageDescription = $club
    ? 'Play today’s free ' . $club['name'] . ' football quiz: five fresh questions covering players, matches, managers, trophies and club history.'
    : 'Play two free daily football games for your club: Daily Five football trivia and Player Wordle. Premier League and Championship challenges every day.';
if (!$club && $selectedGame !== '') {
    $canonicalUrl = 'https://clubdailyfive.com/' . ($selectedGame === 'daily' ? 'daily-football-quiz' : 'player-wordle-game');
    $pageTitle = $selectedGame === 'daily' ? 'Daily Football Quiz – Choose Your Club | ClubDailyFive' : 'Player Wordle – Choose Your Football Club | ClubDailyFive';
    $pageDescription = $selectedGame === 'daily'
        ? 'Choose your Premier League or Championship club and play five fresh football trivia questions every day. Free quizzes, scores and streaks.'
        : 'Choose your Premier League or Championship club and play Player Wordle. Guess today’s mystery footballer in five attempts using coloured clues.';
}
$structuredData = [
    '@context' => 'https://schema.org',
    '@type' => $club ? 'Game' : ($selectedGame !== '' ? 'CollectionPage' : 'WebSite'),
    'name' => $club ? $club['name'] . ' Daily Five' : ($selectedGame !== '' ? $pageTitle : 'ClubDailyFive'),
    'url' => $canonicalUrl,
    'description' => $pageDescription,
    'inLanguage' => 'en-GB',
    'isAccessibleForFree' => true,
];
if (!$club && $selectedGame !== '') {
    $gameItems = [];
    foreach ($clubs as $c) {
        if ($selectedGame === 'wordle' && !isset($wordleReady[wordleSlug($c['slug'])])) continue;
        $gameItems[] = ['@type'=>'ListItem','position'=>count($gameItems)+1,'name'=>$c['name'],
            'url'=>'https://clubdailyfive.com/'.($selectedGame==='daily' ? 'daily-five/'.$c['slug'] : 'player-wordle/'.wordleSlug($c['slug']))];
    }
    $structuredData['mainEntity'] = ['@type'=>'ItemList','itemListElement'=>$gameItems];
}
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07101e">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/assets/icon-192.png">
<?php if (!$club): ?><link rel="stylesheet" href="/assets/game-hub.css?v=20261007-3"><?php endif ?>
<script src="/pwa.js" defer></script><script src="/engagement.js?v=2"></script>
<link rel="canonical" href="<?= h($canonicalUrl) ?>">
<title><?= h($pageTitle) ?></title>
<meta name="description" content="<?= h($pageDescription) ?>">
<meta property="og:type" content="website">
<meta property="og:title" content="<?= h($pageTitle) ?>">
<meta property="og:description" content="<?= h($pageDescription) ?>">
<meta property="og:url" content="<?= h($canonicalUrl) ?>">
<script type="application/ld+json"><?= json_encode($structuredData, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE) ?></script>
<style>
:root{--ink:#f7f8fc;--muted:#a9b2c4;--panel:#111c31;--line:#273650;--accent:<?= h($club['accent'] ?? '#ffcc33') ?>;--good:#2ecc8f;--bad:#ff6475;--bg:#07101e}*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 80% -10%,color-mix(in srgb,var(--accent) 24%,transparent),transparent 36rem),var(--bg);min-height:100vh}.wrap{width:min(760px,calc(100% - 28px));margin:auto}.top{display:flex;align-items:center;justify-content:space-between;padding:22px 0}.brand{display:inline-flex;align-items:center;text-decoration:none;min-width:0}.brand img{display:block;width:clamp(250px,48vw,450px);height:auto}.brand:focus-visible{outline:2px solid var(--accent);outline-offset:5px;border-radius:4px}.date{color:var(--muted);font-size:.82rem}.hero{padding:64px 0 28px}.eyebrow{color:var(--accent);text-transform:uppercase;letter-spacing:.14em;font-weight:800;font-size:.75rem}.hero h1{font-size:clamp(2.7rem,11vw,5.5rem);line-height:.92;letter-spacing:-.07em;margin:.25em 0}.hero p{color:var(--muted);font-size:1.1rem;line-height:1.6;max-width:600px}.club-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:18px 0 64px}.club{min-height:72px;padding:16px;border:1px solid var(--line);border-radius:16px;background:rgba(17,28,49,.72);color:var(--ink);text-decoration:none;font-weight:750;display:flex;align-items:center;justify-content:space-between;transition:.18s}.club:hover,.club:focus-visible{border-color:var(--accent);transform:translateY(-2px);outline:none}.club span{color:var(--muted)}.quiz-head{padding:30px 0 18px}.quiz-head h1{font-size:clamp(2rem,8vw,3.8rem);letter-spacing:-.055em;margin:.2em 0}.progress{display:flex;gap:7px;margin:22px 0}.pip{height:5px;flex:1;background:var(--line);border-radius:99px}.pip.done{background:var(--accent)}.card{border:1px solid var(--line);border-radius:22px;background:rgba(17,28,49,.9);padding:clamp(20px,5vw,34px);min-height:430px;display:flex;flex-direction:column}.count{color:var(--accent);font-weight:800;font-size:.78rem;letter-spacing:.1em;text-transform:uppercase}.question{font-size:clamp(1.45rem,5vw,2rem);line-height:1.18;letter-spacing:-.035em;margin:14px 0 22px;min-height:76px}.answers{display:grid;gap:10px}.answer{width:100%;text-align:left;border:1px solid var(--line);background:#0b1628;color:var(--ink);padding:15px 16px;border-radius:13px;font:inherit;font-weight:680;cursor:pointer;min-height:54px}.answer:hover:not(:disabled){border-color:var(--accent)}.answer.correct{border-color:var(--good);background:color-mix(in srgb,var(--good) 13%,#0b1628)}.answer.wrong{border-color:var(--bad);background:color-mix(in srgb,var(--bad) 13%,#0b1628)}.answer:disabled{cursor:default}.feedback{margin-top:18px;border-top:1px solid var(--line);padding-top:16px;min-height:98px;visibility:hidden;color:var(--muted);line-height:1.5}.feedback.show{visibility:visible}.feedback strong{color:var(--ink)}.feedback a{color:var(--accent)}.correct-confirm{display:flex;align-items:center;justify-content:center;width:46px;height:46px;margin:14px auto 0;border-radius:50%;background:var(--good);color:#04140e;font-size:2rem;font-weight:950;line-height:1;box-shadow:0 0 0 5px color-mix(in srgb,var(--good) 18%,transparent);animation:correct-pop .2s ease-out}@keyframes correct-pop{from{transform:scale(.65);opacity:.2}to{transform:scale(1);opacity:1}}.next{margin-top:auto;align-self:flex-end;background:var(--accent);color:#06101d;border:0;border-radius:12px;padding:12px 20px;font-weight:900;cursor:pointer;visibility:hidden}.next.show{visibility:visible}.result{text-align:center;padding:26px 0}.score{font-size:5rem;font-weight:950;letter-spacing:-.08em;color:var(--accent)}.tiles{font-size:1.65rem;letter-spacing:.1em;margin:10px 0 24px}.share-actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;width:min(520px,100%);margin:20px auto 0}.share-action{min-height:48px;padding:10px 8px;border:1px solid var(--line);border-radius:12px;background:#0b1628;color:var(--ink);font:inherit;font-size:.86rem;font-weight:850;cursor:pointer;text-decoration:none;display:flex;align-items:center;justify-content:center}.share-action:hover,.share-action:focus-visible{border-color:var(--accent);outline:none;transform:translateY(-1px)}.share-action.primary{background:var(--accent);border-color:var(--accent);color:#06101d}@media(max-width:430px){.share-actions{grid-template-columns:repeat(2,1fr)}}.again{display:flex;align-items:center;justify-content:center;gap:10px;width:min(360px,100%);min-height:56px;margin:22px auto 0;padding:14px 20px;border:1px solid color-mix(in srgb,var(--accent) 70%,#fff 10%);border-radius:15px;background:color-mix(in srgb,var(--accent) 13%,#0b1628);color:var(--ink);text-decoration:none;font-weight:900;box-shadow:0 8px 24px rgba(0,0,0,.22);transition:.18s}.again::before{content:'⚽';font-size:1.15rem}.again::after{content:'→';font-size:1.2rem;color:var(--accent)}.again:hover,.again:focus-visible{background:color-mix(in srgb,var(--accent) 22%,#0b1628);border-color:var(--accent);transform:translateY(-2px);outline:none;box-shadow:0 10px 28px rgba(0,0,0,.3)}.foot{color:#778399;font-size:.76rem;padding:36px 0;text-align:center}.foot-links{display:flex;justify-content:center;flex-wrap:wrap;gap:8px 16px;margin-bottom:10px}.foot-links a{color:#a9b2c4;text-decoration:none}.foot-links a:hover,.foot-links a:focus-visible{color:var(--accent);text-decoration:underline}.empty{padding:40px;border:1px solid var(--line);border-radius:20px;background:var(--panel)}@media(min-width:620px){.club-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:430px){.wrap{width:min(100% - 20px,760px)}.top{padding:16px 0}.brand img{width:min(300px,72vw)}.date{font-size:.68rem}.hero{padding-top:38px}.card{min-height:480px;padding:20px}.question{min-height:100px}.feedback{min-height:116px}.answer{min-height:58px}}
/* Hidden must override component display modes when views change. */
[hidden]{display:none!important}
.streak-mini{color:var(--muted);font-size:.78rem;margin-top:5px}.streak-mini b{color:var(--ink)}.streaks{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:390px;margin:18px auto 22px}.streak-box{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:13px}.streak-number{display:block;color:var(--accent);font-size:1.75rem;font-weight:950}.streak-label{color:var(--muted);font-size:.72rem}
/* Responsive crest grid and single-screen mobile quiz */
.club img{width:42px;height:42px;object-fit:contain;flex:0 0 auto}.club-name{line-height:1.1;text-align:right;margin-left:auto}
@media(max-width:600px){body.quiz-page{overflow:hidden}.wrap{width:min(100% - 20px,760px)}.top{height:52px;padding:9px 0}.hero{padding:14px 0 6px}.hero h1{font-size:2.25rem;margin:.15em 0}.hero p{font-size:.82rem;line-height:1.3;margin:.35em 0}.club-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:6px 0 10px}.club{height:88px;min-height:88px;padding:6px 2px 5px;gap:3px;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:48px 26px;justify-content:stretch;justify-items:center;align-items:center;border-radius:10px;font-size:.59rem;box-shadow:none}.club::before{content:none}.club img{grid-area:1/1;display:block;width:42px;height:42px;align-self:center;justify-self:center;object-fit:contain}.club .club-name{grid-area:2/1;color:var(--ink);width:100%;height:26px;margin:0;display:flex;align-items:flex-start;justify-content:center;text-align:center;line-height:1.1;overflow-wrap:normal;word-break:normal;padding-top:1px}.quiz-head{height:98px;padding:7px 0 3px}.quiz-head h1{font-size:1.65rem;margin:.08em 0}.progress{margin:8px 0}.card{height:calc(100dvh - 150px);min-height:0;padding:12px 15px max(12px,env(safe-area-inset-bottom));border-radius:16px;overflow-y:auto;overscroll-behavior:contain}.question{font-size:1.12rem;min-height:50px;margin:7px 0}.answers{gap:6px}.answer{min-height:42px;padding:8px 11px;font-size:.86rem}.feedback{min-height:72px;margin-top:7px;padding-top:7px;font-size:.76rem;line-height:1.25}.next{padding:10px 14px;margin-top:10px;align-self:stretch;min-height:44px;flex:0 0 auto}body.quiz-page .foot{display:none}.home-page .foot{display:block;padding:10px 0 18px}.result{padding:8px 0}.score{font-size:4rem}}
.club{position:relative}.club.played{border-color:var(--good);padding-bottom:29px}.club .played-badge{position:absolute;bottom:5px;left:0;right:0;text-align:center;font-size:.65rem;color:var(--good);font-weight:800}
.share-actions{grid-template-columns:repeat(2,minmax(0,1fr))}
.share-fallback{width:100%;max-width:520px;min-height:110px;margin-top:12px}
@media(max-width:600px){.club.played{padding:6px 2px 19px}.club{height:101px;min-height:101px}.club .played-badge{font-size:.55rem;bottom:3px}body.quiz-page:has(#result:not([hidden])){overflow:auto}}
/* Keep all 20 clubs in four columns and five rows at every viewport width. */
.club-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
/* Club status and streaks stay below each crest on every screen size. */
.club,.club.played{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:42px 2.2em auto;justify-items:center;align-content:start;gap:4px;height:auto;min-height:0;padding:10px 4px}
.club img{grid-area:1/1}
.club .club-name{grid-area:2/1;text-align:center;justify-content:center;align-items:center;display:flex;width:100%;height:auto;margin:0;padding:0;color:var(--ink)}
.club .club-info{grid-area:3/1;display:grid;gap:2px;width:100%;text-align:center;font-size:.7rem;line-height:1.25;font-weight:500}
.club .club-streaks-line{white-space:nowrap}
.club .club-played-tick{position:absolute;top:4px;right:4px;display:flex;align-items:center;justify-content:center;width:18px;height:18px;color:var(--good);font-size:18px;line-height:1;font-weight:900;pointer-events:none}
.club .club-status{font-weight:750}
.club.played .club-status{color:var(--good)}
@media(max-width:600px){.club,.club.played{padding:6px 2px;gap:3px}.club .club-info{font-size:clamp(.5rem,2.1vw,.65rem);letter-spacing:-.02em}}
.info-modal{position:fixed;inset:0;z-index:1400;background:rgba(3,8,16,.82);display:grid;place-items:center;padding:20px}.info-modal[hidden]{display:none!important}.info-dialog{position:relative;width:min(760px,100%);max-height:calc(100dvh - 40px);overflow:auto;border:1px solid var(--line);border-radius:22px;background:#0b1628;padding:clamp(22px,5vw,42px);box-shadow:0 24px 80px rgba(0,0,0,.45)}.info-close{position:absolute;top:12px;right:14px;width:42px;height:42px;border:0;background:transparent;color:var(--ink);font-size:2rem;line-height:1;cursor:pointer;border-radius:50%}.info-close:hover,.info-close:focus-visible{background:var(--panel);outline:2px solid var(--accent)}.info-dialog h1{font-size:clamp(2.2rem,8vw,4rem);letter-spacing:-.055em;margin:.1em 48px .5em 0}.info-dialog h2{font-size:1.2rem;margin-top:1.6em}.info-dialog p,.info-dialog li{color:var(--muted);line-height:1.7}.info-dialog strong{color:var(--ink)}.info-dialog a{color:var(--accent)}.wordle-colour-guide{display:grid;gap:10px;margin:14px 0}.colour-example{display:grid;grid-template-columns:72px 1fr;gap:12px;align-items:start;padding:11px 12px;border:1px solid #273650;border-radius:12px;background:#111c31}.colour-example p{margin:0!important;line-height:1.45!important}.amber-rules{margin:6px 0 7px;padding-left:18px;color:#a9b2c4}.amber-rules li{margin:2px 0;line-height:1.35}.colour-example-note{font-size:.88em}.colour-chip{display:inline-flex;align-items:center;justify-content:center;min-height:32px;border-radius:7px;color:#fff;font-size:.68rem;font-weight:900;letter-spacing:.06em}.colour-green{background:#218d52}.colour-amber{background:#b59f3b;color:#101319}.colour-grey{background:#3a4355}@media(max-width:480px){.colour-example{grid-template-columns:64px 1fr;gap:9px;padding:9px}.colour-example p{font-size:.86rem!important}}body.info-open{overflow:hidden}@media(max-width:600px){.info-modal{padding:0}.info-dialog{width:100%;height:100dvh;max-height:none;border:0;border-radius:0;padding:24px 20px}}
/* Shared ClubDailyFive completed-game hierarchy */
.result{width:min(620px,100%);margin:0 auto;padding:22px 0 30px}
.result>.eyebrow{margin-bottom:5px}
.result .score{line-height:.95;margin:4px 0 8px}
.result h2{margin:4px 0 10px;font-size:clamp(1.45rem,5vw,2rem);letter-spacing:-.03em}
.result .tiles{margin:8px 0 16px}
.result .streaks{margin:14px auto 16px}
.result>p{color:var(--muted);font-size:.88rem;line-height:1.45;max-width:500px;margin:10px auto}
.result .share-actions{grid-template-columns:1fr 1fr;width:min(360px,100%);margin:18px auto 0}
.result .share-action{min-height:52px;border-radius:12px}
.result .again{width:min(360px,100%);margin-top:12px;min-height:54px}
@media(max-width:600px){.result{padding:10px 0 20px}.result .score{font-size:3.6rem}.result .tiles{margin-bottom:11px}.result .streaks{margin:10px auto 12px}.result>p{font-size:.78rem;margin:7px auto}.result .share-actions{margin-top:13px}.result .again{margin-top:10px}}/* Combined two-game progress on club tiles */
.club.one-game-played{border-color:#e7c77a!important;box-shadow:0 0 0 2px rgba(231,199,122,.18),0 10px 24px rgba(0,0,0,.16)!important}
.club.both-games-played{border-color:var(--good)!important;box-shadow:0 0 0 2px rgba(46,204,143,.18),0 10px 24px rgba(0,0,0,.16)!important}.cross-game{width:min(460px,100%);margin:16px auto;padding:14px;border:1px solid #e7c77a;border-radius:16px;background:rgba(231,199,122,.08);display:flex;align-items:center;justify-content:space-between;gap:14px;text-align:left}.cross-game-copy{display:flex;flex-direction:column;gap:3px;min-width:0}.cross-kicker{color:#e7c77a;font-size:.62rem;font-weight:900;letter-spacing:.08em}.cross-game-copy strong{font-size:1rem}.cross-game-copy small{color:var(--muted);line-height:1.25}.cross-game>a{flex:0 0 auto;padding:11px 13px;border-radius:10px;background:#e7c77a;color:#171105;text-decoration:none;font-size:.72rem;font-weight:950}.cross-game.club-complete{border-color:var(--good);background:color-mix(in srgb,var(--good) 9%,transparent);justify-content:center;text-align:center}.cross-game.club-complete .cross-kicker{color:var(--good)}.cross-game.club-complete>a{display:none}@media(max-width:520px){.cross-game{align-items:stretch;flex-direction:column;text-align:center}.cross-game>a{text-align:center}}
/* Keep the information links visible beneath the mobile Daily Five card. */
@media(max-width:600px){
 body.quiz-page .card{height:calc(100dvh - 194px)}
 body.quiz-page .foot{display:block;position:fixed;z-index:30;left:0;right:0;bottom:0;height:44px;padding:8px 10px max(8px,env(safe-area-inset-bottom));background:rgba(7,16,30,.98);border-top:1px solid var(--line)}
 body.quiz-page .foot-links{height:100%;margin:0;gap:5px 14px;align-items:center;font-size:.7rem}
 body.quiz-page .foot>span{display:none}
}

.question-report{margin-top:8px;font-size:.72rem;color:var(--muted)}.question-report summary{cursor:pointer}.report-reasons{display:flex;flex-wrap:wrap;gap:5px;margin:7px 0}.report-reasons button{background:#0b1628;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:9px;cursor:pointer}.report-reasons button:disabled{opacity:.6}
/* League filters for game-specific club selection. */
.league-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;padding:5px;margin:12px 0 20px;border:1px solid var(--line);border-radius:13px;background:#111c31}
.league-tabs button{padding:14px 4px;background:transparent;border:0;border-radius:9px;color:var(--muted);font:inherit;font-size:.85rem;font-weight:800;cursor:pointer}
.league-tabs button[aria-pressed="true"]{background:#ffcc33;color:#07101e}
.league-tabs button:focus-visible{outline:2px solid #fff;outline-offset:2px}
.club[hidden]{display:none!important}
@media(max-width:600px){.league-tabs{margin:8px 0 10px}.league-tabs button{font-size:.7rem;padding:12px 3px}.home-page .club-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
/* Monochrome club crests need light ink on the dark site background. */
img[src*="/assets/crests/derby-county.png"],img[src*="/assets/crests/swansea-city.png"]{filter:brightness(0) invert(1)}
.other-game{display:block;width:min(360px,100%);margin:12px auto 0;padding:11px 14px;border:1px solid #273650;border-radius:12px;color:#f7f8fc;text-decoration:none;font-size:.86rem;text-align:center;background:#111c31}.other-game:hover,.other-game:focus-visible{border-color:#ffcc33}.other-game[hidden]{display:none!important}</style>
</head>
<body class="<?= $club ? 'quiz-page' : ($selectedGame ? 'home-page club-select-page' : 'home-page game-home-page') ?>">
<main class="wrap">
<header class="top"><a class="brand" href="/" aria-label="ClubDailyFive.com home"><img src="/assets/clubdailyfive-logo.svg?v=20261005" alt="ClubDailyFive.com" width="450" height="60"></a><?php if ($club): ?><span class="date"><?= h($dateLabel) ?></span><?php endif ?></header>

<script>
const playDate=<?= json_encode($quizDate) ?>;
try{localStorage.removeItem('dailyfive:player-id');for(const key of Object.keys(localStorage)){if(key.startsWith('dailyfive:counted:')&&!key.includes(`:${playDate}:`))localStorage.removeItem(key)}}catch(e){}
function stored(key){try{return JSON.parse(localStorage.getItem(key))}catch(e){return null}}
function resultKey(slug){return `dailyfive:result:${slug}:${playDate}`}
function clubResult(slug,name){
 const valid=r=>r&&Array.isArray(r.marks)&&r.marks.length===5;
 let r=stored(resultKey(slug));if(valid(r))return r;
 const old=stored(`dailyfive:daily:${playDate}`);
 r=old&&(old.clubSlug===slug||old.club===name)?old:stored(`dailyfive:${name}:${playDate}`);
 if(!valid(r))return null;
 const streak=stored(`dailyfive:streaks:${name}`)||{};
 r={...r,club:name,clubSlug:slug,completion:r.completion??streak.completion??0,perfect:r.perfect??streak.perfect??0};
 localStorage.setItem(resultKey(slug),JSON.stringify(r));return r;
}
function londonDate(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function checkDay(){if(londonDate()!==playDate){location.reload();return false}return true}
window.addEventListener('pageshow',()=>checkDay());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkDay()});
setInterval(checkDay,30000);
</script>

<?php if (!$club && $slug !== ''): ?>
<section class="empty"><h1>Club not found</h1><p>Choose one of the available clubs.</p><a class="again" href="/daily-football-quiz">Choose a club</a></section>
<?php elseif (!$club && $selectedGame === ''): ?>
<section class="game-home-intro" aria-labelledby="homeTitle"><h1 id="homeTitle">Your club. Your daily challenge.</h1><p>Choose a game to get started.</p></section>
<section class="game-tiles" aria-label="Choose your daily football game">
<a class="game-tile" href="/daily-football-quiz" aria-labelledby="dailyTileTitle"><div class="tile-art tile-art-daily" aria-hidden="true"></div><div class="tile-copy"><h2 id="dailyTileTitle">Daily Five</h2><p>5 questions. How well do you know your club?</p><span class="tile-action">Play Daily Five <span aria-hidden="true">→</span></span></div></a>
<a class="game-tile" href="/player-wordle-game" aria-labelledby="wordleTileTitle"><div class="tile-art tile-art-wordle" aria-hidden="true"></div><div class="tile-copy"><h2 id="wordleTileTitle">Player Wordle</h2><p>1 mystery player. 5 guesses.</p><span class="tile-action">Play Player Wordle <span aria-hidden="true">→</span></span></div></a>
</section>
<p class="daily-return">New challenges every day <span>· Premier League &amp; Championship</span></p>
<?php elseif (!$club): ?>
<nav class="hub-back" aria-label="Back to games"><a href="/">← Games</a></nav>
<section class="club-select-intro"><h1><?= $selectedGame === 'daily' ? 'Daily Five' : 'Player Wordle' ?></h1><p>Choose your club.</p></section>
<nav class="league-tabs" aria-label="Choose a league">
<?php foreach(['premier-league'=>'Premier League','championship'=>'Championship'] as $key=>$label): ?><button type="button" data-league="<?=h($key)?>" aria-pressed="<?=$key==='premier-league'?'true':'false'?>"><?=h($label)?></button><?php endforeach ?>
</nav>
<h2 class="visually-hidden" id="leagueTitle">All clubs</h2>
<section class="club-grid" aria-label="Choose your club"><?php foreach($clubs as $c):
$ready = $selectedGame === 'daily' || isset($wordleReady[wordleSlug($c['slug'])]);
$gameUrl = $selectedGame === 'daily' ? '/daily-five/'.$c['slug'] : '/player-wordle/'.wordleSlug($c['slug']);
?>
<?php if ($ready): ?><a class="club" data-slug="<?=h($c['slug'])?>" data-name="<?=h($c['name'])?>" data-league="<?=h($c['league'])?>" href="<?=h($gameUrl)?>">
<?php else: ?><div class="club preparing-club" data-league="<?=h($c['league'])?>" aria-label="<?=h($c['name'])?>: player bank in preparation"><?php endif ?>
<img src="<?=h($c['logo_path'])?>" alt="" width="52" height="52"><span class="club-name"><?=h($c['name'])?></span>
<?php if (!$ready): ?><span class="club-info">Coming soon</span></div><?php else: ?></a><?php endif ?>
<?php endforeach ?></section>
<p class="selection-note">New challenges at midnight UK time. Your progress and streaks are saved on this device.</p>
<details class="game-explainer"><summary>How <?= $selectedGame === 'daily' ? 'Daily Five' : 'Player Wordle' ?> works</summary>
<?php if ($selectedGame === 'daily'): ?><p>Answer five multiple-choice football questions about your club’s players, matches, managers and history. See the correct answer and explanation after each choice, then share your score. Come back tomorrow for a fresh quiz.</p>
<?php else: ?><p>Guess your club’s mystery footballer in five attempts. Each guess reveals coloured clues for debut age, position, nationality, debut year and previous clubs. Green means a match; amber helps you narrow down the answer. <a href="/how-it-works">Read the colour guide</a>.</p><?php endif ?>
<p>Explore <a href="/<?= $selectedGame === 'daily' ? 'player-wordle-game' : 'daily-football-quiz' ?>"><?= $selectedGame === 'daily' ? 'Player Wordle' : 'Daily Five' ?></a> or <a href="/">return to the games</a>.</p>
</details>
<details class="club-directory"><summary>Club history and quiz guides</summary><nav aria-label="Club guides"><?php foreach($clubs as $c): ?><a href="/clubs/<?=h($c['slug'])?>"><?=h($c['name'])?></a><?php endforeach ?></nav></details>
<script>
const selectedGame=<?=json_encode($selectedGame)?>;
const pwSlugMap={'coventry-city':'coventry','hull-city':'hull','ipswich-town':'ipswich','leeds-united':'leeds','manchester-city':'man-city','manchester-united':'man-utd','newcastle-united':'newcastle','tottenham-hotspur':'tottenham'};
function markClubs(){
 const yesterday=new Date(playDate+'T12:00:00Z');yesterday.setUTCDate(yesterday.getUTCDate()-1);
 const prev=yesterday.toISOString().slice(0,10),active=d=>d===playDate||d===prev;
 document.querySelectorAll('.club[data-slug]').forEach(el=>{
  const slug=el.dataset.slug,name=el.dataset.name,pw=pwSlugMap[slug]||slug;
  const r=clubResult(slug,name),s=stored('dailyfive:streaks:'+name)||{};
  const ps=stored('pw:'+pw)||{},pg=stored('pwgame:'+playDate+':'+pw)||{};
  const progress=stored('dailyfive:progress:'+slug+':'+playDate);
  const done=selectedGame==='daily'?!!r:((ps.date===playDate&&ps.done===true)||pg.done===true);
  const started=selectedGame==='daily'?!!(progress&&Array.isArray(progress.marks)&&progress.marks.length):Number(pg.attempts)>0;
  const streak=selectedGame==='daily'?(r?(r.completion??s.completion):active(s.lastCompleted)?s.completion:0):(active(ps.date)?ps.streak:0);
  const perfect=selectedGame==='daily'?(r?(r.perfect??s.perfect):active(s.lastCompleted)&&active(s.lastPerfect)?s.perfect:0):0;
  el.classList.toggle('played',done);el.classList.toggle('in-progress',!done&&started);
  let tick=el.querySelector('.club-played-tick');
  if(done&&!tick){tick=document.createElement('span');tick.className='club-played-tick';tick.textContent='✓';tick.setAttribute('aria-hidden','true');el.appendChild(tick)}
  if(!done&&tick)tick.remove();
  let info=el.querySelector('.club-info');if(!info){info=document.createElement('span');info.className='club-info';el.appendChild(info)}
  const status=done?'Completed today':started?'In progress today':'';
  const streakText=Number(streak)>0?'🔥 '+Math.max(0,Math.floor(streak))+(Number(perfect)>0?' · ⭐ '+Math.floor(perfect):''):'';
  info.textContent=[status,streakText].filter(Boolean).join(' · ');info.hidden=!info.textContent;
  el.setAttribute('aria-label',name+': '+(status||'Play '+(selectedGame==='daily'?'Daily Five':'Player Wordle'))+(Number(streak)>0?'. Completion streak: '+streak+' days':''));
 });
}
function chooseLeague(key){
 const tab=document.querySelector('.league-tabs button[data-league="'+key+'"]');
 if(!tab){key='premier-league'}
 document.querySelectorAll('.league-tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.league===key)));
 document.querySelectorAll('.club[data-league]').forEach(c=>c.hidden=c.dataset.league!==key);
 document.getElementById('leagueTitle').textContent=document.querySelector('.league-tabs button[data-league="'+key+'"]').textContent;
 try{localStorage.setItem('cdf:league',key)}catch(e){}
}
let rememberedLeague='premier-league';try{rememberedLeague=localStorage.getItem('cdf:league')||rememberedLeague}catch(e){}
chooseLeague(rememberedLeague);
document.querySelectorAll('.league-tabs button').forEach(b=>b.addEventListener('click',()=>chooseLeague(b.dataset.league)));
markClubs();window.addEventListener('pageshow',markClubs);window.addEventListener('storage',markClubs);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)markClubs()});
document.querySelectorAll('.club[data-slug]').forEach(el=>el.addEventListener('click',()=>cdfEvent(el.dataset.slug,selectedGame,'selected')));
</script>
<?php elseif (count($questions) !== 5): ?>
<section class="quiz-head"><div class="eyebrow">DAILY FIVE · <?= h($club['name']) ?></div><h1>Today’s five</h1></section><div class="empty"><h2>The next round is being prepared.</h2><p>Come back shortly for five fresh questions.</p><a class="again" href="/daily-football-quiz">Back to club selection</a></div>
<?php else: ?>
<section class="quiz-head" id="quizHead"><div class="eyebrow">DAILY FIVE · <?= h($club['name']) ?></div><h1>Today’s five</h1><div class="streak-mini" id="streakMini" hidden></div><div class="progress" id="progress" aria-label="Quiz progress"></div></section>
<section class="card" id="quiz" aria-live="polite"><div class="count" id="count"></div><h2 class="question" id="question"></h2><div class="answers" id="answers"></div><div class="feedback" id="feedback"></div><details id="reportQuestion" class="question-report"><summary>Report this question</summary><div class="report-reasons"><button type="button" data-reason="incorrect">Incorrect answer</button><button type="button" data-reason="outdated">Outdated statistic</button><button type="button" data-reason="repeated">Repeated question</button></div><small id="reportStatus" role="status"></small></details><button class="next" id="next">Next question</button></section>
<section class="result" id="result" hidden><div class="eyebrow">Full time</div><div class="score" id="score"></div><h2 id="resultClub"><?= h($club['name']) ?> Daily Five</h2><div class="tiles" id="tiles"></div><div class="streaks"><div class="streak-box"><span class="streak-number" id="completionStreak">0</span><span class="streak-label">🔥 completion streak</span></div><div class="streak-box"><span class="streak-number" id="perfectStreak">0</span><span class="streak-label">⭐ perfect 5/5 streak</span></div></div><p>You’ve played this club today. Try another club, or return after midnight UK time.</p><div class="share-actions" aria-label="Share your result"><button class="share-action primary" id="shareNative">Share result</button><button class="share-action" id="shareCopy">Copy result</button></div><p id="shareStatus" role="status"></p><textarea id="shareFallback" class="share-fallback" aria-label="Result to copy" readonly hidden></textarea><?php if(isset($wordleReady[wordleSlug($club['slug'])])):?><a class="other-game" id="otherGame" href="/player-wordle/<?=h(wordleSlug($club['slug']))?>">Try today’s Player Wordle →</a><?php endif?><a class="again" href="/daily-football-quiz">Back to club selection</a></section>
<script>
const questions=<?= json_encode(array_map(fn($q)=>['id'=>(int)$q['id'],'q'=>$q['question_text'],'o'=>json_decode($q['options_json'],true),'a'=>(int)$q['correct_index'],'e'=>$q['explanation'],'u'=>$q['source_url'],'s'=>$q['source_label']],$questions), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE) ?>;
const club=<?= json_encode($club['name']) ?>, clubSlug=<?= json_encode($club['slug']) ?>, quizDate=<?= json_encode($quizDate) ?>, roundId=questions.map(x=>x.id).join('-');
cdfEvent(clubSlug,'daily','selected');
const sourceQuizDate=<?= json_encode($sourceQuizDate) ?>;
function track(event,questionId=null){
 if(['started','completed'].includes(event))cdfEvent(clubSlug,'daily',event);
 const send=()=>fetch('/track.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({club:clubSlug,event,question_id:questionId,quiz_date:sourceQuizDate,play_date:playDate,analytics_version:2}),keepalive:true}).catch(()=>{});
 if(event==='shown'){send();return}
 const key=`dailyfive:counted:${clubSlug}:${playDate}:${event}`;
 const once=()=>{try{if(localStorage.getItem(key))return;localStorage.setItem(key,'1')}catch(e){return}return send()};
 if(navigator.locks){navigator.locks.request(key,once).catch(()=>{})}else{once()}
}
let at=0,score=0,marks=[],resultData=null;const $=id=>document.getElementById(id);
const streakKey=`dailyfive:streaks:${club}`;
const dailyKey=resultKey(clubSlug);
const progressKey=`dailyfive:progress:${clubSlug}:${quizDate}`;
function yesterday(date){const d=new Date(`${date}T12:00:00Z`);d.setUTCDate(d.getUTCDate()-1);return d.toISOString().slice(0,10)}
function readStreaks(){try{return JSON.parse(localStorage.getItem(streakKey))||{completion:0,perfect:0}}catch(e){return{completion:0,perfect:0}}}
function showReturningStreak(){const s=readStreaks();if(s.completion||s.perfect){$('streakMini').innerHTML=`🔥 <b>${s.completion||0}</b> completed &nbsp; ⭐ <b>${s.perfect||0}</b> perfect`;$('streakMini').hidden=false}}
function updateStreaks(){let s=readStreaks();if(s.lastCompleted!==quizDate){const prev=yesterday(quizDate);s.completion=s.lastCompleted===prev?(s.completion||0)+1:1;s.lastCompleted=quizDate;if(score===5){s.perfect=s.lastPerfect===prev?(s.perfect||0)+1:1;s.lastPerfect=quizDate}else{s.perfect=0;s.lastPerfect=null}localStorage.setItem(streakKey,JSON.stringify(s))}return s}
function readDailyResult(){return clubResult(clubSlug,club)}
function showResult(r){const other=$('otherGame');if(other){try{const pw=JSON.parse(localStorage.getItem('pw:'+({ 'coventry-city':'coventry','hull-city':'hull','ipswich-town':'ipswich','leeds-united':'leeds','manchester-city':'man-city','manchester-united':'man-utd','newcastle-united':'newcastle','tottenham-hotspur':'tottenham'}[clubSlug]||clubSlug))||'{}'),round=JSON.parse(localStorage.getItem('pwgame:'+playDate+':'+({ 'coventry-city':'coventry','hull-city':'hull','ipswich-town':'ipswich','leeds-united':'leeds','manchester-city':'man-city','manchester-united':'man-utd','newcastle-united':'newcastle','tottenham-hotspur':'tottenham'}[clubSlug]||clubSlug))||'{}');other.hidden=(pw.date===playDate&&pw.done===true)||round.done===true}catch(e){}}resultData=r;score=Number(r.score)||0;marks=Array.isArray(r.marks)?r.marks:[];$('quiz').hidden=true;$('quizHead').hidden=true;$('result').hidden=false;$('score').textContent=`${score}/5`;$('resultClub').textContent=`${r.club||club} Daily Five`;$('tiles').textContent=marks.map(x=>x?'🟩':'⬛').join('');$('completionStreak').textContent=r.completion||0;$('perfectStreak').textContent=r.perfect||0}
$('progress').innerHTML=questions.map((_,i)=>`<span class="pip" id="p${i}"></span>`).join('');
function render(){const x=questions[at];$('reportQuestion').open=false;$('reportStatus').textContent='';document.querySelectorAll('[data-reason]').forEach(b=>b.disabled=false);track('shown',x.id);$('count').textContent=`Question ${at+1} of 5`;$('question').textContent=x.q;$('answers').innerHTML='';$('feedback').className='feedback';$('feedback').innerHTML='';$('next').className='next';x.o.forEach((label,i)=>{const b=document.createElement('button');b.className='answer';b.textContent=label;b.onclick=()=>choose(i);$('answers').appendChild(b)});}
function choose(i){if(!checkDay())return;if(at===0&&marks.length===0)track('started');const done=readDailyResult();if(done){showResult(done);return}if(marks.length>at)return;const x=questions[at],buttons=[...document.querySelectorAll('.answer')];buttons.forEach((b,n)=>{b.disabled=true;if(n===x.a)b.classList.add('correct');if(n===i&&i!==x.a)b.classList.add('wrong')});const ok=i===x.a;if(ok)score++;marks.push(ok);localStorage.setItem(progressKey,JSON.stringify({roundId,marks,score}));$('feedback').innerHTML=`<strong>${ok?'Correct.':'Not quite.'}</strong> ${x.e} <a href="${x.u}" target="_blank" rel="noopener">${x.s} ↗</a>${ok?'<span class="correct-confirm" aria-label="Correct answer">✓</span>':''}`;$('feedback').classList.add('show');$('next').textContent=at===4?'See result':'Next question';$('next').classList.add('show');document.getElementById(`p${at}`).classList.add('done');}
document.querySelectorAll('[data-reason]').forEach(b=>b.onclick=async()=>{
 const buttons=[...document.querySelectorAll('[data-reason]')];buttons.forEach(x=>x.disabled=true);$('reportStatus').textContent='Sending…';
 try{const r=await fetch('/engagement.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({club:clubSlug,event:'report',question_id:questions[at].id,quiz_date:sourceQuizDate,reason:b.dataset.reason})});if(!r.ok)throw Error();$('reportStatus').textContent='Thanks — your report has been saved for review.'}
 catch(e){$('reportStatus').textContent='Could not send. Please try again.';buttons.forEach(x=>x.disabled=false)}
});
$('next').onclick=()=>{if(!checkDay()||marks.length!==at+1)return;if(++at<questions.length)render();else finish()};
function finish(){const saved=readDailyResult();if(saved){showResult(saved);return}track('completed');localStorage.setItem(`dailyfive:${club}:${quizDate}`,JSON.stringify({score,marks}));const s=updateStreaks();const r={club,clubSlug,roundId,score,marks,completion:s.completion||0,perfect:s.perfect||0};localStorage.setItem(dailyKey,JSON.stringify(r));localStorage.removeItem(progressKey);showResult(r)}
function currentShare(){
 const r=resultData||{club,clubSlug,score,marks,completion:0,perfect:0};
 const url=`https://clubdailyfive.com/?club=${encodeURIComponent(r.clubSlug||clubSlug)}`;
 const message=`ClubDailyFive.com — ${r.club||club}
${quizDate}  ${r.score}/5
${r.marks.map(x=>x?'🟩':'⬛').join('')}
🔥 ${r.completion||0} day streak  ⭐ ${r.perfect||0} perfect

Can you beat me?
${url}`;
 return {url,message};
}

async function copyResult(){const message=currentShare().message;
 try{await navigator.clipboard.writeText(message);cdfEvent(clubSlug,'daily','shared');$('shareStatus').textContent='Result copied! Paste it into a message.'}
 catch(e){$('shareFallback').hidden=false;$('shareFallback').value=message;$('shareFallback').focus();$('shareFallback').select();$('shareStatus').textContent='Select and copy your result below.'}
}
$('shareNative').onclick=async()=>{
 if(navigator.share){try{await navigator.share({text:currentShare().message});cdfEvent(clubSlug,'daily','shared');return}catch(e){if(e.name==='AbortError')return}}
 await copyResult();
};
$('shareCopy').onclick=copyResult;
const completed=readDailyResult();
if(completed)showResult(completed);else{
 const progress=stored(progressKey);
 if(progress&&progress.roundId===roundId&&Array.isArray(progress.marks)&&progress.marks.length<=5){
  marks=progress.marks;score=marks.filter(Boolean).length;at=marks.length;
  if(at>0)localStorage.setItem(`dailyfive:counted:${clubSlug}:${playDate}:started`,'1');
 }
 if(at===5)finish();else{showReturningStreak();render()}
}
window.addEventListener('storage',()=>{const r=readDailyResult();if(r)showResult(r);else{const p=stored(progressKey);if(p&&p.roundId===roundId&&p.marks.length>marks.length)location.reload()}});
window.addEventListener('pageshow',()=>{const r=readDailyResult();if(r)showResult(r)});

</script>
<?php endif ?>
<footer class="foot"><nav class="foot-links" aria-label="Site information"><a href="/daily-football-quiz">Football quiz</a><a href="/player-wordle-game">Player Wordle</a><a href="/about">About</a><a href="/how-it-works">How it works</a><a href="/privacy">Privacy Policy</a><a href="/contact">Contact</a></nav><span>Independent supporter quiz. Not affiliated with or endorsed by the Premier League or any club.</span><p class="sistersite" style="margin:10px 0 0;font-size:12px;line-height:1.6;color:inherit">More football fun: <a href="https://predictioncomp.com/" style="color:inherit;text-decoration:underline;text-underline-offset:3px">PredictionComp</a> · predict Premier League scores &amp; beat the bots</p></footer>
<div class="info-modal" id="infoModal" hidden aria-hidden="true"><article class="info-dialog" role="dialog" aria-modal="true" aria-labelledby="infoTitle"><button class="info-close" id="infoClose" type="button" aria-label="Close">×</button><div id="infoContent"></div></article></div>
<script>
(()=>{const modal=document.getElementById('infoModal'),content=document.getElementById('infoContent'),close=document.getElementById('infoClose');let scrollY=0,lastFocus=null;
async function openInfo(a){lastFocus=a;scrollY=window.scrollY;document.body.classList.add('info-open');modal.hidden=false;modal.setAttribute('aria-hidden','false');content.innerHTML='<p>Loading…</p>';try{const r=await fetch(a.href,{cache:'no-store',headers:{'X-ClubDailyFive-Overlay':'1'}});if(!r.ok)throw new Error();content.innerHTML=await r.text();history.pushState({info:true},'',a.getAttribute('href'));close.focus()}catch(e){location.href=a.href}}
function closeInfo(fromPop=false){modal.hidden=true;modal.setAttribute('aria-hidden','true');document.body.classList.remove('info-open');window.scrollTo(0,scrollY);if(!fromPop)history.back();if(lastFocus)lastFocus.focus()}
document.querySelectorAll('.foot-links a').forEach(a=>{if(['/about','/how-it-works','/privacy','/contact'].includes(a.getAttribute('href')))a.addEventListener('click',e=>{e.preventDefault();openInfo(a)})});close.addEventListener('click',()=>closeInfo());modal.addEventListener('click',e=>{if(e.target===modal)closeInfo()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!modal.hidden)closeInfo()});window.addEventListener('popstate',()=>{if(!modal.hidden)closeInfo(true)});
})();
</script>
</main>
</body></html>
