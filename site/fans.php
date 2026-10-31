<?php
// Club fan table: today's, this week's and all-time Daily Five scores for fans of one club.
declare(strict_types=1);
require __DIR__ . '/leagues-lib.php';
header('Cache-Control: no-store');

$slug = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($_GET['club'] ?? ''))) ?? '';
$club = lg_clubs()[$slug] ?? null;
if (!$club) { header('Location: /leagues', true, 302); exit; }

$dist = lg_distribution($slug);
$tables = [];
foreach (['today', 'week', 'all'] as $p) $tables[$p] = lg_table($p, 'p.home_club=?', [$slug], 100);
$name = $club['name'];
lg_page_head($name . ' Fan Table – Daily Five | ClubDailyFive', "Today's top $name fans in the Daily Five quiz, plus this week's and all-time tables.", (string)$club['accent']);
$maxBar = max(1, max($dist['dist']));
?>
<section class="lg-hero">
  <?php if ($club['logo_path']): ?><img class="lg-crest" src="<?= lg_h($club['logo_path']) ?>" alt="" width="72" height="72"><?php endif ?>
  <div><div class="eyebrow">Daily Five fan table</div><h1><?= lg_h($name) ?> fans</h1></div>
</section>

<section class="lg-card lg-today-summary">
  <h2>Today</h2>
  <?php if ($dist['played'] > 0): ?>
    <p class="lg-lede"><b><?= (int)$dist['played'] ?></b> <?= $dist['played'] === 1 ? 'player has' : 'players have' ?> played today’s <?= lg_h($name) ?> Daily Five · average score <b><?= lg_h(number_format((float)$dist['average'], 1)) ?></b></p>
    <div class="lg-dist" role="img" aria-label="Score spread today"><?php foreach ($dist['dist'] as $s => $n): ?><div class="lg-bar" data-score="<?= $s ?>"><span style="height:<?= (int)round(100 * $n / $maxBar) ?>%"></span><b><?= $s ?></b><small><?= (int)$n ?></small></div><?php endforeach ?></div>
  <?php else: ?>
    <p class="lg-lede">Nobody has played today’s <?= lg_h($name) ?> Daily Five yet. Be first on the table.</p>
  <?php endif ?>
  <a class="lg-button primary" href="/daily-five/<?= lg_h($slug) ?>">Play today’s <?= lg_h($name) ?> Daily Five</a>
</section>

<div class="lg-setup" data-setup data-club="<?= lg_h($slug) ?>"></div>

<section class="lg-card">
  <div class="lg-tabs" role="tablist">
    <button role="tab" aria-selected="true" data-tab="today">Today</button><button role="tab" aria-selected="false" data-tab="week">This week</button><button role="tab" aria-selected="false" data-tab="all">All time</button>
  </div>
  <div data-panel="today"><?php lg_render_table($tables['today'], 'today', false, 'No named ' . $name . ' fans have played today yet.') ?></div>
  <div data-panel="week" hidden><?php lg_render_table($tables['week'], 'week', false, 'No rounds this week yet. Weeks run Monday to Sunday.') ?></div>
  <div data-panel="all" hidden><?php lg_render_table($tables['all'], 'all', false, 'No rounds yet.') ?></div>
  <p class="lg-note">Only rounds of <?= lg_h($name) ?>’s quiz from fans who picked <?= lg_h($name) ?> as their club count. Everyone gets the same five questions each day.</p>
</section>

<section class="lg-card lg-cta">
  <h2>Play against your mates</h2>
  <p>Start a private league, share the link in your group chat, and see who knows their club best. Friends can support different clubs: each plays their own club’s Daily Five.</p>
  <a class="lg-button" href="/leagues">Private leagues</a>
</section>

<nav class="lg-other" aria-label="Other fan tables"><h2>Other fan tables</h2><?php foreach (lg_clubs() as $c): if ($c['league'] !== $club['league'] || $c['slug'] === $slug) continue; ?><a href="/fans/<?= lg_h($c['slug']) ?>"><?= lg_h($c['name']) ?></a><?php endforeach ?></nav>
<script>window.CDF_CLUBS=<?= json_encode(array_values(array_map(fn($c) => ['slug' => $c['slug'], 'name' => $c['name'], 'league' => $c['league']], lg_clubs())), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?>;</script>
<?php lg_page_foot();
