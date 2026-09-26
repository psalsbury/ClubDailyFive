<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
const DB_PATH = '/var/lib/clubdailyfive/clubquiz.sqlite';
function h(string $v): string { return htmlspecialchars($v, ENT_QUOTES, 'UTF-8'); }
function playerSlug(string $slug): string {
    return ['coventry-city'=>'coventry','hull-city'=>'hull','ipswich-town'=>'ipswich','leeds-united'=>'leeds','manchester-city'=>'man-city','manchester-united'=>'man-utd','newcastle-united'=>'newcastle','tottenham-hotspur'=>'tottenham'][$slug] ?? $slug;
}
$pdo = new PDO('sqlite:' . DB_PATH, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$clubs = $pdo->query("SELECT slug,name,logo_path FROM clubs WHERE active=1 ORDER BY name")->fetchAll(PDO::FETCH_ASSOC);
$type = (string)($_GET['type'] ?? '');
$slug = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($_GET['club'] ?? '')));
$club = null;
foreach ($clubs as $candidate) if ($candidate['slug'] === $slug) $club = $candidate;
$facts = [
 'arsenal'=>'Test your knowledge of Arsenal players, managers, trophies and memorable matches from Highbury to the Emirates era.',
 'aston-villa'=>'Explore Aston Villa history, European success, famous players and memorable matches from Villa Park.',
 'bournemouth'=>'Challenge yourself on AFC Bournemouth’s rise, managers, players and landmark matches.',
 'brentford'=>'Test your Brentford knowledge across Griffin Park, the Community Stadium, players and recent seasons.',
 'brighton'=>'Explore Brighton & Hove Albion players, managers, promotions and memorable matches.',
 'chelsea'=>'Challenge yourself on Chelsea trophies, managers, transfers, players and Stamford Bridge history.',
 'coventry-city'=>'Test your knowledge of Coventry City history, cup runs, famous players and memorable matches.',
 'crystal-palace'=>'Explore Crystal Palace players, managers, Selhurst Park moments and club history.',
 'everton'=>'Challenge yourself on Everton trophies, Goodison Park, famous players and historic matches.',
 'fulham'=>'Test your Fulham knowledge across Craven Cottage, players, managers and memorable seasons.',
 'hull-city'=>'Explore Hull City promotions, cup runs, managers, players and memorable matches.',
 'ipswich-town'=>'Challenge yourself on Ipswich Town’s league, FA Cup and European history and famous figures.',
 'leeds-united'=>'Test your knowledge of Leeds United players, managers, trophies and Elland Road history.',
 'liverpool'=>'Explore Liverpool trophies, European nights, managers, players and iconic Anfield matches.',
 'manchester-city'=>'Challenge yourself on Manchester City history, trophies, record-breaking teams and famous players.',
 'manchester-united'=>'Test your Manchester United knowledge across managers, trophies, players and Old Trafford history.',
 'newcastle-united'=>'Explore Newcastle United players, managers, St James’ Park and memorable matches.',
 'nottingham-forest'=>'Challenge yourself on Nottingham Forest’s European triumphs, managers, players and City Ground history.',
 'sunderland'=>'Test your Sunderland knowledge across Roker Park, the Stadium of Light, players and famous matches.',
 'tottenham-hotspur'=>'Explore Tottenham Hotspur trophies, managers, players and memorable matches from across the decades.',
];
if ($type === 'club' && !$club) { http_response_code(404); $type = 'missing'; }
if ($type === 'club') {
    $title = $club['name'].' Football Quiz – Daily Five & Player Wordle';
    $description = 'Play free '.$club['name'].' football quizzes: answer five daily trivia questions and guess the mystery player in Player Wordle.';
    $canonical = 'https://clubdailyfive.com/clubs/'.$club['slug'];
    $heading = $club['name'].' Football Quiz';
} elseif ($type === 'wordle') {
    $title = 'Player Wordle – Guess the Footballer | ClubDailyFive';
    $description = 'Play Player Wordle for your football club. Guess the mystery player in five attempts using debut, position and nationality clues.';
    $canonical = 'https://clubdailyfive.com/player-wordle-game';
    $heading = 'Player Wordle';
} else {
    $title = 'Daily Football Quiz – Five Questions Every Day | ClubDailyFive';
    $description = 'Choose your club and answer five fresh football questions every day covering players, matches, managers, transfers and trophies.';
    $canonical = 'https://clubdailyfive.com/daily-football-quiz';
    $heading = 'Daily Football Quiz';
}
$jsonLd = ['@context'=>'https://schema.org','@type'=>'WebPage','name'=>$title,'url'=>$canonical,'description'=>$description,'inLanguage'=>'en-GB','isPartOf'=>['@type'=>'WebSite','name'=>'ClubDailyFive','url'=>'https://clubdailyfive.com/']];
?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#07101e"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="canonical" href="<?=h($canonical)?>"><title><?=h($title)?></title><meta name="description" content="<?=h($description)?>"><meta property="og:type" content="website"><meta property="og:title" content="<?=h($title)?>"><meta property="og:description" content="<?=h($description)?>"><meta property="og:url" content="<?=h($canonical)?>"><script type="application/ld+json"><?=json_encode($jsonLd,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE)?></script>
<style>:root{--ink:#f7f8fc;--muted:#a9b2c4;--panel:#111c31;--line:#273650;--accent:#38d879;--blue:#54a8ff;--bg:#07101e}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% -10%,rgba(56,216,121,.16),transparent 36rem),var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif}.wrap{width:min(980px,calc(100% - 28px));margin:auto}.top{display:flex;align-items:center;justify-content:space-between;padding:20px 0}.brand img{width:min(410px,70vw);height:auto}.crumbs{font-size:.8rem;color:var(--muted)}.crumbs a{color:var(--muted)}.hero{text-align:center;padding:38px 0 26px}.hero-logo{width:110px;height:110px;object-fit:contain}.eyebrow{color:var(--accent);font-size:.75rem;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.hero h1{font-size:clamp(2.4rem,8vw,5rem);line-height:.96;letter-spacing:-.055em;margin:.2em 0}.hero p{max-width:700px;margin:14px auto;color:var(--muted);font-size:1.08rem;line-height:1.65}.games{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0 34px}.game{border:1px solid var(--line);border-radius:20px;background:rgba(17,28,49,.9);padding:24px}.game h2{font-size:1.6rem;margin:0 0 8px}.game p{color:var(--muted);line-height:1.55}.button{display:inline-flex;margin-top:10px;padding:13px 17px;border-radius:11px;background:var(--accent);color:#062014;text-decoration:none;font-weight:900}.wordle .button{background:var(--blue);color:#061323}.content{border-top:1px solid var(--line);padding:28px 0}.content h2{font-size:1.7rem}.content p,.content li{color:var(--muted);line-height:1.7}.clubs{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.club{display:flex;align-items:center;gap:8px;padding:10px;border:1px solid var(--line);border-radius:12px;color:var(--ink);text-decoration:none;background:rgba(17,28,49,.7);font-size:.82rem;font-weight:750}.club img{width:34px;height:34px;object-fit:contain}.foot{text-align:center;color:#778399;font-size:.76rem;padding:28px 0}.foot a{color:#a9b2c4;margin:0 7px}@media(max-width:650px){.games{grid-template-columns:1fr}.clubs{grid-template-columns:repeat(2,1fr)}.hero{padding-top:20px}.hero p{font-size:.96rem}.top{padding:14px 0}}</style></head><body><main class="wrap"><header class="top"><a class="brand" href="/"><img src="/assets/clubdailyfive-logo.svg" alt="ClubDailyFive.com" width="410" height="55"></a></header><nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> › <?=h($heading)?></nav>
<?php if ($type==='missing'): ?><section class="hero"><h1>Club not found</h1><p>Choose an available club from the homepage.</p><a class="button" href="/">Choose a club</a></section>
<?php elseif ($type==='club'): ?><section class="hero"><img class="hero-logo" src="<?=h($club['logo_path'])?>" alt="<?=h($club['name'])?> crest"><div class="eyebrow">Free daily football games</div><h1><?=h($heading)?></h1><p><?=h($facts[$club['slug']] ?? $description)?></p></section><section class="games"><article class="game"><h2><?=h($club['name'])?> Daily Five</h2><p>Answer five fresh questions covering club history, players, managers, matches, transfers, trophies and recent football.</p><a class="button" href="/daily-five/<?=h($club['slug'])?>">Play Daily Five →</a></article><article class="game wordle"><h2><?=h($club['name'])?> Player Wordle</h2><p>Identify today’s mystery player in five guesses. Each attempt reveals clues to help narrow down the answer.</p><a class="button" href="/player-wordle/<?=h(playerSlug($club['slug']))?>">Play Player Wordle →</a></article></section><section class="content"><h2>New <?=h($club['name'])?> challenges every day</h2><p>Daily Five draws on a reviewed bank of club questions and recent match information. Player Wordle selects a mystery player from the club’s eligible player database. Both games reset at midnight UK time, remember your progress on this device and are free to play.</p><h2>Topics in the <?=h($club['name'])?> quiz</h2><ul><li>Historic and recent matches</li><li>Players, managers and leading scorers</li><li>Trophies and knockout competitions</li><li>Transfers, attendances and club records</li></ul></section>
<?php else: ?><section class="hero"><div class="eyebrow">A fresh challenge every day</div><h1><?=h($heading)?></h1><p><?=h($description)?></p></section><section class="content"><h2>Choose a club</h2><div class="clubs"><?php foreach($clubs as $c): ?><a class="club" href="/clubs/<?=h($c['slug'])?>"><img src="<?=h($c['logo_path'])?>" alt="" width="34" height="34"><span><?=h($c['name'])?></span></a><?php endforeach ?></div><h2>How it works</h2><?php if($type==='wordle'): ?><p>Choose your club and type a player’s name. The coloured clues compare debut age, position, nationality, debut year and previous clubs with the mystery player. You have five guesses.</p><?php else: ?><p>Choose your club and answer five multiple-choice questions. You receive the correct answer and explanation after each choice, then a shareable score and streak when the round is complete.</p><?php endif ?></section><?php endif ?>
<footer class="foot"><a href="/about">About</a><a href="/how-it-works">How it works</a><a href="/privacy">Privacy</a><a href="/contact">Contact</a><p>Independent supporter quiz. Not affiliated with or endorsed by the Premier League or any club.</p></footer></main></body></html>
