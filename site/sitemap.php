<?php
declare(strict_types=1);
header('Content-Type: application/xml; charset=UTF-8');
$pdo = new PDO('sqlite:/var/lib/clubdailyfive/clubquiz.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$clubs = $pdo->query("SELECT slug FROM clubs WHERE active=1 ORDER BY slug")->fetchAll(PDO::FETCH_COLUMN);
$base = 'https://clubdailyfive.com';
$urls = ['/', '/daily-football-quiz', '/player-wordle-game', '/about', '/how-it-works', '/privacy', '/contact'];
foreach ($clubs as $slug) {
    $urls[] = '/clubs/' . rawurlencode((string)$slug);
    $urls[] = '/daily-five/' . rawurlencode((string)$slug);
    $playerSlug = ['coventry-city'=>'coventry','hull-city'=>'hull','ipswich-town'=>'ipswich','leeds-united'=>'leeds','manchester-city'=>'man-city','manchester-united'=>'man-utd','newcastle-united'=>'newcastle','tottenham-hotspur'=>'tottenham'][$slug] ?? $slug;
    $urls[] = '/player-wordle/' . rawurlencode((string)$playerSlug);
}
echo '<?xml version="1.0" encoding="UTF-8"?>', "\n";
?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<?php foreach ($urls as $url): ?>  <url><loc><?= htmlspecialchars($base . $url, ENT_XML1|ENT_QUOTES, 'UTF-8') ?></loc></url>
<?php endforeach ?></urlset>
