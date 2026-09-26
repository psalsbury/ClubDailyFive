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
$clubs = $pdo->query("SELECT slug,name,accent,logo_path FROM clubs WHERE active=1 ORDER BY name")->fetchAll(PDO::FETCH_ASSOC);
$slug = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($_GET['club'] ?? '')));
$club = null;
if ($slug !== '') {
    $stmt = $pdo->prepare('SELECT id,slug,name,accent,logo_path FROM clubs WHERE slug=? AND active=1');
    $stmt->execute([$slug]);
    $club = $stmt->fetch(PDO::FETCH_ASSOC) ?: null;
}

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
    : 'Play two free daily football games for your club: Daily Five football trivia and Player Wordle. Fresh challenges for 20 clubs every day.';
$structuredData = [
    '@context' => 'https://schema.org',
    '@type' => $club ? 'Game' : 'WebSite',
    'name' => $club ? $club['name'] . ' Daily Five' : 'ClubDailyFive',
    'url' => $canonicalUrl,
    'description' => $pageDescription,
    'inLanguage' => 'en-GB',
    'isAccessibleForFree' => true,
];
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
<script src="/pwa.js" defer></script>
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
.info-modal{position:fixed;inset:0;z-index:1000;background:rgba(3,8,16,.82);display:grid;place-items:center;padding:20px}.info-modal[hidden]{display:none!important}.info-dialog{position:relative;width:min(760px,100%);max-height:calc(100dvh - 40px);overflow:auto;border:1px solid var(--line);border-radius:22px;background:#0b1628;padding:clamp(22px,5vw,42px);box-shadow:0 24px 80px rgba(0,0,0,.45)}.info-close{position:absolute;top:12px;right:14px;width:42px;height:42px;border:0;background:transparent;color:var(--ink);font-size:2rem;line-height:1;cursor:pointer;border-radius:50%}.info-close:hover,.info-close:focus-visible{background:var(--panel);outline:2px solid var(--accent)}.info-dialog h1{font-size:clamp(2.2rem,8vw,4rem);letter-spacing:-.055em;margin:.1em 48px .5em 0}.info-dialog h2{font-size:1.2rem;margin-top:1.6em}.info-dialog p,.info-dialog li{color:var(--muted);line-height:1.7}.info-dialog strong{color:var(--ink)}.info-dialog a{color:var(--accent)}body.info-open{overflow:hidden}@media(max-width:600px){.info-modal{padding:0}.info-dialog{width:100%;height:100dvh;max-height:none;border:0;border-radius:0;padding:24px 20px}}
.game-picker{position:fixed;inset:0;z-index:1200;background:#07111a;display:grid;place-items:center}.game-picker[hidden]{display:none!important}.game-picker-card{position:relative;width:min(540px,100%);height:100dvh;overflow:hidden;background:radial-gradient(circle at 50% 31%,rgba(120,20,20,.34),transparent 27%),linear-gradient(180deg,#07131e 0%,#0b1721 43%,#07130e 100%);padding:20px 18px max(18px,env(safe-area-inset-bottom));display:flex;flex-direction:column}.game-picker-card:before{content:'';position:absolute;inset:18% 0 34%;background:linear-gradient(180deg,transparent,rgba(255,255,255,.035),transparent);pointer-events:none}.picker-brand{position:relative;z-index:1;display:flex;justify-content:center;align-items:center;gap:10px;color:#fff;font-size:clamp(1.1rem,5vw,1.45rem);font-weight:950;letter-spacing:-.03em;margin:4px 0 12px}.picker-brand span{font-size:1.5rem}.picker-brand em{color:#38d879;font-style:normal}.picker-close{position:absolute;z-index:4;right:16px;top:16px;border:0;background:rgba(0,0,0,.28);color:#fff;width:38px;height:38px;border-radius:50%;font-size:1.8rem;line-height:1;cursor:pointer}.picker-head{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;text-align:center;gap:7px;padding:0 42px 16px}.picker-head img{width:clamp(88px,15vh,130px);height:clamp(88px,15vh,130px);object-fit:contain;filter:drop-shadow(0 5px 10px rgba(0,0,0,.3))}.picker-head h2{margin:0;color:#fff;font-size:clamp(1.35rem,5.8vw,1.9rem);line-height:1.05;text-transform:uppercase;letter-spacing:.015em;font-weight:950}.games-panel{position:relative;z-index:2;margin-top:clamp(8px,2vh,18px);background:linear-gradient(180deg,rgba(25,42,61,.98),rgba(13,27,40,.99));border:1px solid #38516a;border-radius:28px 28px 0 0;padding:18px 14px 14px;box-shadow:0 -8px 35px rgba(0,0,0,.4)}.games-panel:before{content:'';display:block;width:52px;height:6px;border-radius:5px;background:#6d8093;margin:-7px auto 13px}.game-choice{display:block;position:relative;text-decoration:none;color:#12243a;background:#f6f7f9;border:1px solid #cdd7e0;border-radius:17px;padding:15px 14px 12px;margin-top:12px;box-shadow:0 4px 10px rgba(0,0,0,.2)}.game-choice-top{display:grid;grid-template-columns:52px minmax(0,1fr) auto;grid-template-rows:auto auto;column-gap:10px;align-items:center}.game-icon{grid-column:1;grid-row:1 / span 2;font-size:2.25rem;text-align:center}.game-choice strong{grid-column:2;grid-row:1;font-size:1.12rem;line-height:1.1;font-weight:950;letter-spacing:-.02em}.game-score{grid-column:3;grid-row:1;color:#172b42;font-weight:950;font-size:.92rem}.game-state{grid-column:2 / 4;grid-row:2;color:#e25722;font-size:.78rem;font-weight:900;margin-top:5px}.game-state:empty{display:none}.game-choice p{margin:3px 0 9px 62px;color:#46566a;font-size:.84rem;line-height:1.25}.play-bar{display:flex;align-items:center;justify-content:center;gap:14px;width:100%;border-radius:12px;padding:11px 12px;color:#fff;font-size:.9rem;font-weight:950;letter-spacing:.015em}.daily-card .play-bar{background:#f02431}.wordle-card .play-bar{background:#1469ee}.play-bar b{font-size:1.25rem}.club-combo{display:flex;align-items:center;justify-content:space-between;margin-top:13px;padding:10px 12px;border:1px solid #2d8d49;background:rgba(2,31,16,.74);border-radius:13px;color:#fff}.club-combo span{display:grid;grid-template-columns:auto 1fr;column-gap:7px;align-items:center;font-size:.77rem}.club-combo span>b{font-size:.75rem}.club-combo small{grid-column:2;color:#a8b6ad;font-size:.63rem}.club-combo>strong{color:#ffb124;font-size:.9rem;white-space:nowrap}body.picker-open{overflow:hidden}@media(min-width:650px){.game-picker{background:rgba(3,8,16,.88)}.game-picker-card{height:min(860px,94dvh);border:1px solid #38516a;border-radius:28px;box-shadow:0 30px 90px rgba(0,0,0,.65)}.games-panel{border-radius:28px}}@media(max-height:720px){.game-picker-card{padding-top:10px}.picker-brand{margin-bottom:5px}.picker-head{padding-bottom:7px}.picker-head img{width:70px;height:70px}.games-panel{padding-top:12px}.game-choice{padding:10px;margin-top:8px}.game-choice p{margin-bottom:6px}.play-bar{padding:8px}.club-combo{margin-top:8px;padding:7px 10px}}/* Balanced two-game homepage */
.home-page .wrap{width:min(1080px,calc(100% - 28px))}
.home-page .top{padding-bottom:12px}
.home-intro{text-align:center;padding:26px 0 12px}
.home-intro .eyebrow{color:#38d879}
.home-intro h1{font-size:clamp(2.25rem,7vw,4.6rem);line-height:.98;letter-spacing:-.055em;margin:.18em auto .48em;max-width:900px}
.home-intro h1 span{color:#38d879}
.home-intro>p{color:var(--muted);font-size:clamp(.95rem,2.3vw,1.15rem);line-height:1.5;max-width:720px;margin:12px auto 20px}
.home-games{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0 auto 24px}
.home-game{position:relative;overflow:hidden;text-align:left;border:1px solid var(--line);border-radius:20px;padding:20px;background:linear-gradient(145deg,rgba(17,28,49,.98),rgba(8,18,31,.96));min-height:172px}
.home-game.daily{border-color:rgba(46,204,143,.55)}
.home-game.wordle{border-color:rgba(47,148,255,.6)}
.home-game-head{display:flex;align-items:center;gap:11px;margin-bottom:8px}
.home-game-icon{width:46px;height:46px;display:grid;place-items:center;border-radius:50%;font-size:1.55rem;background:rgba(46,204,143,.15)}
.wordle .home-game-icon{background:rgba(47,148,255,.16)}
.home-game h2{font-size:1.55rem;letter-spacing:-.035em;margin:0}
.home-game strong{display:block;color:#38d879;font-size:.78rem;margin-bottom:7px}
.home-game.wordle strong{color:#54a8ff}
.home-game p{color:var(--muted);font-size:.9rem;line-height:1.4;margin:0}
.choose-title{text-align:center;margin:18px 0 4px;font-size:clamp(1.25rem,4vw,1.75rem);letter-spacing:-.03em}
.choose-sub{text-align:center;color:var(--muted);font-size:.84rem;margin:0 0 10px}
.home-page .club-grid{padding:8px 0 28px;gap:8px}
@media(min-width:800px){.home-page .club-grid{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(max-width:600px){.home-page .top{height:auto;padding:10px 0}.home-page .brand img{width:min(270px,68vw)}.home-intro{padding:8px 0 5px}.home-intro h1{font-size:2rem}.home-intro>p{font-size:.76rem;line-height:1.3;margin:7px auto 10px}.home-games{gap:7px;margin-bottom:10px}.home-game{min-height:112px;padding:10px;border-radius:13px}.home-game-head{gap:7px;margin-bottom:3px}.home-game-icon{width:32px;height:32px;font-size:1.05rem}.home-game h2{font-size:1.05rem}.home-game strong{font-size:.6rem;margin-bottom:3px}.home-game p{font-size:.63rem;line-height:1.22}.choose-title{font-size:1.05rem;margin:8px 0 1px}.choose-sub{font-size:.64rem;margin-bottom:4px}.home-page .club-grid{padding:3px 0 8px}}
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
.club.both-games-played{border-color:var(--good)!important;box-shadow:0 0 0 2px rgba(46,204,143,.18),0 10px 24px rgba(0,0,0,.16)!important}.cross-game{width:min(460px,100%);margin:16px auto;padding:14px;border:1px solid #e7c77a;border-radius:16px;background:rgba(231,199,122,.08);display:flex;align-items:center;justify-content:space-between;gap:14px;text-align:left}.cross-game-copy{display:flex;flex-direction:column;gap:3px;min-width:0}.cross-kicker{color:#e7c77a;font-size:.62rem;font-weight:900;letter-spacing:.08em}.cross-game-copy strong{font-size:1rem}.cross-game-copy small{color:var(--muted);line-height:1.25}.cross-game>a{flex:0 0 auto;padding:11px 13px;border-radius:10px;background:#e7c77a;color:#171105;text-decoration:none;font-size:.72rem;font-weight:950}.cross-game.club-complete{border-color:var(--good);background:color-mix(in srgb,var(--good) 9%,transparent);justify-content:center;text-align:center}.cross-game.club-complete .cross-kicker{color:var(--good)}.cross-game.club-complete>a{display:none}@media(max-width:520px){.cross-game{align-items:stretch;flex-direction:column;text-align:center}.cross-game>a{text-align:center}}</style>
</head>
<body class="<?= $club ? 'quiz-page' : 'home-page' ?>">
<main class="wrap">
<header class="top"><a class="brand" href="/" aria-label="ClubDailyFive.com home"><img src="/assets/clubdailyfive-logo.svg" alt="ClubDailyFive.com" width="450" height="60"></a><span class="date"><?= h($dateLabel) ?></span></header>

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

<?php if (!$club): ?>
<div id="homeChooser">
<section class="home-intro">
<div class="eyebrow">Two daily football games · All 20 clubs</div>
<h1>Your club. <span>Two ways to play.</span></h1>

<div class="home-games">
<article class="home-game daily"><div class="home-game-head"><span class="home-game-icon">🧠</span><h2>Daily Five</h2></div><strong>5 QUESTIONS · EVERY DAY</strong><p>History, matches, players, managers, transfers and more. Five fresh challenges for your chosen club.</p></article>
<article class="home-game wordle"><div class="home-game-head"><span class="home-game-icon">👕</span><h2>Player Wordle</h2></div><strong>1 MYSTERY PLAYER · 5 GUESSES</strong><p>Use the clues from each guess to work out today's hidden player for your chosen club.</p></article>
</div>
<h2 class="choose-title">Choose your club</h2>
<p class="choose-sub">Then choose which game you want to play.</p>
</section>
<section class="club-grid" aria-label="Choose your club"><?php foreach($clubs as $c): ?><a class="club" data-slug="<?= h($c['slug']) ?>" data-name="<?= h($c['name']) ?>" data-logo="<?= h($c['logo_path']) ?>" href="/clubs/<?= h($c['slug']) ?>"><img src="<?= h($c['logo_path']) ?>" alt="<?= h($c['name']) ?> crest" width="42" height="42"><span class="club-name"><?= h($c['name']) ?></span></a><?php endforeach ?></section></div>
<div class="game-picker" id="gamePicker" hidden aria-hidden="true"><section class="game-picker-card" role="dialog" aria-modal="true" aria-labelledby="pickerClub"><button class="picker-close" id="pickerClose" type="button" aria-label="Close">×</button><div class="picker-brand"><span>⚽</span><b>CLUB <em>DAILY</em> FIVE</b></div><div class="picker-head"><img id="pickerLogo" src="" alt=""><div><h2 id="pickerClub"></h2></div></div><div class="games-panel"><a class="game-choice daily-card" id="dailyFiveChoice" href="#"><div class="game-choice-top"><span class="game-icon">🧠</span><strong>DAILY FIVE</strong><span class="game-score" id="dailyScore"></span><span class="game-state" id="dailyFiveState"></span></div><p id="dailyFiveDesc">Five questions about your club.</p><span class="play-bar">PLAY DAILY FIVE <b>→</b></span></a><a class="game-choice wordle-card" id="playerWordleChoice" href="#"><div class="game-choice-top"><span class="game-icon">👕</span><strong>PLAYER WORDLE</strong><span class="game-score" id="wordleScore"></span><span class="game-state" id="playerWordleState"></span></div><p id="playerWordleDesc">Guess today's player.</p><span class="play-bar">PLAY PLAYER WORDLE <b>→</b></span></a><div class="club-combo" id="clubCombo"><span>🏆 <b>CLUB STREAK</b><small>Complete both games to keep your streak</small></span><strong id="comboStreak">🔥 —</strong></div></div></section></div>
<script>
function markClubs(){document.querySelectorAll('.club[data-slug]').forEach(el=>{
 const r=clubResult(el.dataset.slug,el.dataset.name);
 const s=stored(`dailyfive:streaks:${el.dataset.name}`)||{};
 const d=new Date(`${playDate}T12:00:00Z`);d.setUTCDate(d.getUTCDate()-1);
 const prev=d.toISOString().slice(0,10);
 const active=date=>date===playDate||date===prev;
 const count=value=>Math.max(0,Math.floor(Number(value)||0));
 const completion=count(r?(r.completion??s.completion):(active(s.lastCompleted)?s.completion:0));
 const perfect=count(r?(r.perfect??s.perfect):(active(s.lastCompleted)&&active(s.lastPerfect)?s.perfect:0));
 const progress=stored(`dailyfive:progress:${el.dataset.slug}:${playDate}`);
 const started=progress&&Array.isArray(progress.marks)&&progress.marks.length>0;
 const status=r?'':started?'In progress today':'';
 const pwMap={'manchester-city':'man-city','manchester-united':'man-utd','newcastle-united':'newcastle','tottenham-hotspur':'tottenham'};
 let pw={};try{pw=JSON.parse(localStorage.getItem('pw:'+(pwMap[el.dataset.slug]||el.dataset.slug))||'{}')}catch(e){}
 const dailyDone=!!r,wordleDone=pw.date===playDate&&pw.done===true;
 el.classList.toggle('played',dailyDone&&wordleDone);
 el.classList.toggle('one-game-played',dailyDone!==wordleDone);
 el.classList.toggle('both-games-played',dailyDone&&wordleDone);
 let tick=el.querySelector('.club-played-tick');
 if(dailyDone&&wordleDone&&!tick){tick=document.createElement('span');tick.className='club-played-tick';tick.textContent='✓';tick.setAttribute('aria-hidden','true');tick.title='Both games completed today';el.appendChild(tick)}
 if(!(dailyDone&&wordleDone)&&tick)tick.remove();
 let info=el.querySelector('.club-info');
 if(!info){info=document.createElement('span');info.className='club-info';
 for(const cls of ['club-status','club-streaks-line']){const line=document.createElement('span');line.className=cls;info.appendChild(line)}
 el.appendChild(info)}
 info.querySelector('.club-status').textContent=status;
 info.querySelector('.club-status').hidden=!status;
 const streaks=info.querySelector('.club-streaks-line');
 streaks.textContent=`🔥 ${completion} · ⭐ ${perfect}`;
 streaks.hidden=!(completion>0||perfect>0);
 streaks.title=`Completion streak: ${completion} days; perfect 5/5 streak: ${perfect} days`;
 info.hidden=!status&&streaks.hidden;
 el.setAttribute('aria-label',`${el.dataset.name}: ${r?`Played today, ${r.score} out of 5`:status||'Not played today'}. Completion streak: ${completion} days. Perfect streak: ${perfect} days.`);
})}
markClubs();window.addEventListener('pageshow',markClubs);window.addEventListener('storage',markClubs);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)markClubs()});
const pwSlugMap={'manchester-city':'man-city','manchester-united':'man-utd','newcastle-united':'newcastle','tottenham-hotspur':'tottenham'};
function pwSlug(slug){return pwSlugMap[slug]||slug}
function pwStatus(slug){let s={},g={};const p=pwSlug(slug);try{s=JSON.parse(localStorage.getItem('pw:'+p)||'{}');g=JSON.parse(localStorage.getItem('pwgame:'+playDate+':'+p)||'{}')}catch(e){}if(s.date===playDate&&s.done)return '✓ COMPLETED';if(g.attempts>0&&!g.done)return 'IN PROGRESS';return s.streak>0?'🔥 '+s.streak+' STREAK':''}
function closePicker(){const p=document.getElementById('gamePicker');p.hidden=true;p.setAttribute('aria-hidden','true');document.body.classList.remove('picker-open')}
function openPicker(el){const slug=el.dataset.slug,name=el.dataset.name,shortName=name.replace(/^Nottingham /,'').replace(/^Manchester /,'').replace(/ United$/,'').replace(/ City$/,'');document.getElementById('pickerClub').textContent=name;document.getElementById('dailyFiveDesc').textContent=`5 questions about ${shortName}`;document.getElementById('playerWordleDesc').textContent=`Guess today's ${shortName} player`;document.getElementById('pickerLogo').src=el.dataset.logo;document.getElementById('pickerLogo').alt=name+' crest';document.getElementById('dailyFiveChoice').href='/daily-five/'+encodeURIComponent(slug);document.getElementById('playerWordleChoice').href='/player-wordle/game.php?club='+encodeURIComponent(pwSlug(slug));const r=clubResult(slug,name),ds=stored(`dailyfive:streaks:${name}`)||{},ps=pwStatus(slug),dailyStreak=Number(ds.completion)||0;document.getElementById('dailyScore').textContent=r?`✓ ${r.score}/5`:'';document.getElementById('dailyFiveState').textContent=dailyStreak?`🔥 ${dailyStreak} day streak`:(r?'✓ Completed today':'');document.getElementById('wordleScore').textContent=ps.includes('COMPLETED')?'✓ 5/5':'';document.getElementById('playerWordleState').textContent=ps.replace('✓ COMPLETED','Completed today');const pwRaw=(()=>{try{return JSON.parse(localStorage.getItem('pw:'+pwSlug(slug))||'{}')}catch(e){return {}}})();const combo=(r&&ps.includes('COMPLETED'))?Math.min(dailyStreak||1,Number(pwRaw.streak)||1):0;document.getElementById('comboStreak').textContent=combo?`🔥 ${combo} days`:'🔥 —';const p=document.getElementById('gamePicker');p.hidden=false;p.setAttribute('aria-hidden','false');document.body.classList.add('picker-open');document.getElementById('pickerClose').focus()}
document.querySelectorAll('.club[data-slug]').forEach(el=>el.addEventListener('click',e=>{e.preventDefault();openPicker(el)}));
document.getElementById('pickerClose').addEventListener('click',closePicker);document.getElementById('gamePicker').addEventListener('click',e=>{if(e.target.id==='gamePicker')closePicker()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closePicker()});
</script>
<?php elseif (count($questions) !== 5): ?>
<section class="quiz-head"><div class="eyebrow">DAILY FIVE · <?= h($club['name']) ?></div><h1>Today’s five</h1></section><div class="empty"><h2>The next round is being prepared.</h2><p>Come back shortly for five fresh questions.</p><a class="again" href="/">Back to club selection</a></div>
<?php else: ?>
<section class="quiz-head" id="quizHead"><div class="eyebrow">DAILY FIVE · <?= h($club['name']) ?></div><h1>Today’s five</h1><div class="streak-mini" id="streakMini" hidden></div><div class="progress" id="progress" aria-label="Quiz progress"></div></section>
<section class="card" id="quiz" aria-live="polite"><div class="count" id="count"></div><h2 class="question" id="question"></h2><div class="answers" id="answers"></div><div class="feedback" id="feedback"></div><button class="next" id="next">Next question</button></section>
<section class="result" id="result" hidden><div class="eyebrow">Full time</div><div class="score" id="score"></div><h2 id="resultClub"><?= h($club['name']) ?> Daily Five</h2><div class="tiles" id="tiles"></div><div class="streaks"><div class="streak-box"><span class="streak-number" id="completionStreak">0</span><span class="streak-label">🔥 completion streak</span></div><div class="streak-box"><span class="streak-number" id="perfectStreak">0</span><span class="streak-label">⭐ perfect 5/5 streak</span></div></div><p>You’ve played this club today. Try another club, or return after midnight UK time.</p><div class="share-actions" aria-label="Share your result"><button class="share-action primary" id="shareNative">Share result</button><button class="share-action" id="shareCopy">Copy result</button></div><p id="shareStatus" role="status"></p><textarea id="shareFallback" class="share-fallback" aria-label="Result to copy" readonly hidden></textarea><a class="again" href="/">Back to club selection</a></section>
<script>
const questions=<?= json_encode(array_map(fn($q)=>['id'=>(int)$q['id'],'q'=>$q['question_text'],'o'=>json_decode($q['options_json'],true),'a'=>(int)$q['correct_index'],'e'=>$q['explanation'],'u'=>$q['source_url'],'s'=>$q['source_label']],$questions), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE) ?>;
const club=<?= json_encode($club['name']) ?>, clubSlug=<?= json_encode($club['slug']) ?>, quizDate=<?= json_encode($quizDate) ?>, roundId=questions.map(x=>x.id).join('-');
const sourceQuizDate=<?= json_encode($sourceQuizDate) ?>;
function track(event,questionId=null){
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
function showResult(r){resultData=r;score=Number(r.score)||0;marks=Array.isArray(r.marks)?r.marks:[];$('quiz').hidden=true;$('quizHead').hidden=true;$('result').hidden=false;$('score').textContent=`${score}/5`;$('resultClub').textContent=`${r.club||club} Daily Five`;$('tiles').textContent=marks.map(x=>x?'🟩':'⬛').join('');$('completionStreak').textContent=r.completion||0;$('perfectStreak').textContent=r.perfect||0}
$('progress').innerHTML=questions.map((_,i)=>`<span class="pip" id="p${i}"></span>`).join('');
function render(){const x=questions[at];track('shown',x.id);$('count').textContent=`Question ${at+1} of 5`;$('question').textContent=x.q;$('answers').innerHTML='';$('feedback').className='feedback';$('feedback').innerHTML='';$('next').className='next';x.o.forEach((label,i)=>{const b=document.createElement('button');b.className='answer';b.textContent=label;b.onclick=()=>choose(i);$('answers').appendChild(b)});}
function choose(i){if(!checkDay())return;const done=readDailyResult();if(done){showResult(done);return}if(marks.length>at)return;const x=questions[at],buttons=[...document.querySelectorAll('.answer')];buttons.forEach((b,n)=>{b.disabled=true;if(n===x.a)b.classList.add('correct');if(n===i&&i!==x.a)b.classList.add('wrong')});const ok=i===x.a;if(ok)score++;marks.push(ok);localStorage.setItem(progressKey,JSON.stringify({roundId,marks,score}));$('feedback').innerHTML=`<strong>${ok?'Correct.':'Not quite.'}</strong> ${x.e} <a href="${x.u}" target="_blank" rel="noopener">${x.s} ↗</a>${ok?'<span class="correct-confirm" aria-label="Correct answer">✓</span>':''}`;$('feedback').classList.add('show');$('next').textContent=at===4?'See result':'Next question';$('next').classList.add('show');document.getElementById(`p${at}`).classList.add('done');}
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
 try{await navigator.clipboard.writeText(message);$('shareStatus').textContent='Result copied! Paste it into a message.'}
 catch(e){$('shareFallback').hidden=false;$('shareFallback').value=message;$('shareFallback').focus();$('shareFallback').select();$('shareStatus').textContent='Select and copy your result below.'}
}
$('shareNative').onclick=async()=>{
 if(navigator.share){try{await navigator.share({text:currentShare().message});return}catch(e){if(e.name==='AbortError')return}}
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
 if(at===5)finish();else{track('started');showReturningStreak();render()}
}
window.addEventListener('storage',()=>{const r=readDailyResult();if(r)showResult(r);else{const p=stored(progressKey);if(p&&p.roundId===roundId&&p.marks.length>marks.length)location.reload()}});
window.addEventListener('pageshow',()=>{const r=readDailyResult();if(r)showResult(r)});

</script>
<?php endif ?>
<footer class="foot"><nav class="foot-links" aria-label="Site information"><a href="/about">About</a><a href="/how-it-works">How it works</a><a href="/privacy">Privacy Policy</a><a href="/contact">Contact</a></nav><span>Independent supporter quiz. Not affiliated with or endorsed by the Premier League or any club.</span></footer>
<div class="info-modal" id="infoModal" hidden aria-hidden="true"><article class="info-dialog" role="dialog" aria-modal="true" aria-labelledby="infoTitle"><button class="info-close" id="infoClose" type="button" aria-label="Close">×</button><div id="infoContent"></div></article></div>
<script>
(()=>{const modal=document.getElementById('infoModal'),content=document.getElementById('infoContent'),close=document.getElementById('infoClose');let scrollY=0,lastFocus=null;
async function openInfo(a){lastFocus=a;scrollY=window.scrollY;document.body.classList.add('info-open');modal.hidden=false;modal.setAttribute('aria-hidden','false');content.innerHTML='<p>Loading…</p>';try{const r=await fetch(a.href,{headers:{'X-ClubDailyFive-Overlay':'1'}});if(!r.ok)throw new Error();content.innerHTML=await r.text();history.pushState({info:true},'',a.getAttribute('href'));close.focus()}catch(e){location.href=a.href}}
function closeInfo(fromPop=false){modal.hidden=true;modal.setAttribute('aria-hidden','true');document.body.classList.remove('info-open');window.scrollTo(0,scrollY);if(!fromPop&&location.pathname!=='/')history.back();if(lastFocus)lastFocus.focus()}
document.querySelectorAll('.foot-links a').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();openInfo(a)}));close.addEventListener('click',()=>closeInfo());modal.addEventListener('click',e=>{if(e.target===modal)closeInfo()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!modal.hidden)closeInfo()});window.addEventListener('popstate',()=>{if(!modal.hidden)closeInfo(true)});
})();
</script>
</main>
</body></html>
