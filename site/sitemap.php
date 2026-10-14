<?php
declare(strict_types=1);
header('Content-Type: application/xml; charset=UTF-8');
$pdo = new PDO('sqlite:/var/lib/clubdailyfive/clubquiz.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$clubs = $pdo->query("SELECT slug FROM clubs WHERE active=1 ORDER BY slug")->fetchAll(PDO::FETCH_COLUMN);
$wordle = new PDO('sqlite:/var/lib/clubdailyfive/player-wordle/game.sqlite3');
$wordleClubs = array_fill_keys($wordle->query('SELECT c.slug FROM clubs c JOIN players p ON p.club_id=c.id GROUP BY c.id HAVING count(p.id)>=10')->fetchAll(PDO::FETCH_COLUMN), true);
$base = 'https://clubdailyfive.com';
// Use published round dates rather than claiming an update on every request.
$today = (new DateTimeImmutable('now', new DateTimeZone('Europe/London')))->format('Y-m-d');
$quizDates = $pdo->query("SELECT c.slug,MAX(d.quiz_date) AS updated FROM clubs c JOIN daily_questions d ON d.club_id=c.id WHERE d.quiz_date<=date('now') GROUP BY c.slug")->fetchAll(PDO::FETCH_KEY_PAIR);
$playerDates = $wordle->query("SELECT c.slug,MAX(d.game_date) AS updated FROM clubs c JOIN daily_game d ON d.club_id=c.id WHERE d.game_date<=date('now') GROUP BY c.slug")->fetchAll(PDO::FETCH_KEY_PAIR);
$modified = [];
$templateDate = date('Y-m-d', (int)filemtime(__DIR__.'/seo.php'));
$urls = ['/', '/daily-football-quiz', '/player-wordle-game', '/about', '/how-it-works', '/privacy', '/contact'];
foreach ($clubs as $slug) {
    $clubUrl = '/clubs/' . rawurlencode((string)$slug);
    $urls[] = $clubUrl;
    $modified[$clubUrl] = max($templateDate, $quizDates[$slug] ?? $templateDate);
    $dailyUrl = '/daily-five/' . rawurlencode((string)$slug);
    $urls[] = $dailyUrl;
    if (isset($quizDates[$slug])) $modified[$dailyUrl] = $quizDates[$slug];
    $playerSlug = ['coventry-city'=>'coventry','hull-city'=>'hull','ipswich-town'=>'ipswich','leeds-united'=>'leeds','manchester-city'=>'man-city','manchester-united'=>'man-utd','newcastle-united'=>'newcastle','tottenham-hotspur'=>'tottenham'][$slug] ?? $slug;
    if (isset($wordleClubs[$playerSlug])) {
        $playerUrl = '/player-wordle/' . rawurlencode((string)$playerSlug);
        $urls[] = $playerUrl;
        if (isset($playerDates[$playerSlug])) $modified[$playerUrl] = $playerDates[$playerSlug];
    }
}
echo '<?xml version="1.0" encoding="UTF-8"?>', "\n";
?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<?php foreach ($urls as $url): ?>  <url><loc><?= htmlspecialchars($base . $url, ENT_XML1|ENT_QUOTES, 'UTF-8') ?></loc><?php if (isset($modified[$url])): ?><lastmod><?= htmlspecialchars($modified[$url], ENT_XML1, 'UTF-8') ?></lastmod><?php endif ?></url>
<?php endforeach ?></urlset>
