<?php
// /club-table: which club's fans know their club best? Average Daily Five score per club.
declare(strict_types=1);
require __DIR__ . '/leagues-lib.php';
header('Cache-Control: no-store');

$periods = ['today' => 'Today', 'week' => 'This week', 'all' => 'All time'];
$tables = [];
foreach ($periods as $p => $_) $tables[$p] = lg_club_table($p);
$leagueNames = ['premier-league' => 'Premier League', 'championship' => 'Championship'];
$rivalPairs = [];
foreach (LG_RIVALS as $a => $b) { if ((LG_RIVALS[$b] ?? '') !== $a) continue; $k = [$a, $b]; sort($k); $rivalPairs[implode('|', $k)] = $k; }

lg_page_head('Club Table – Which Fans Know Their Club Best? | ClubDailyFive', 'Every club’s fans ranked by their average Daily Five quiz score: today, this week and all time. Premier League and Championship.');
?>
<section class="lg-hero"><div><div class="eyebrow">Daily Five · club v club</div><h1>Club table</h1><p class="lg-lede">Which fans know their club best? Clubs are ranked by the average Daily Five score of everyone who played their quiz. Each club has its own questions, so it’s a bit of fun rather than a fair contest.</p></div></section>

<section class="lg-card">
  <div class="lg-tabs" role="tablist"><?php $first = true; foreach ($periods as $p => $label): ?><button role="tab" aria-selected="<?= $first ? 'true' : 'false' ?>" data-tab="<?= $p ?>"><?= $label ?></button><?php $first = false; endforeach ?></div>
  <div class="lg-filter" role="group" aria-label="League"><button type="button" aria-pressed="true" data-league-filter="">All clubs</button><button type="button" aria-pressed="false" data-league-filter="premier-league">Premier League</button><button type="button" aria-pressed="false" data-league-filter="championship">Championship</button></div>
  <?php $first = true; foreach ($periods as $p => $label): $t = $tables[$p]; ?>
  <div data-panel="<?= $p ?>"<?= $first ? '' : ' hidden' ?>>
    <?php if ($t['ranked']): ?>
    <ol class="lg-table lg-clubs">
      <?php foreach ($t['ranked'] as $r): ?>
      <li data-league="<?= lg_h($r['league']) ?>" data-club="<?= lg_h($r['slug']) ?>"><span class="lg-pos"><?= $r['joint'] ? '=' : '' ?><?= (int)$r['rank'] ?></span>
        <a class="lg-name" href="/fans/<?= lg_h($r['slug']) ?>"><?php if ($r['logo']): ?><img src="<?= lg_h($r['logo']) ?>" alt="" width="26" height="26" loading="lazy"><?php endif ?><span><?= lg_h($r['name']) ?><small><?= lg_h($leagueNames[$r['league']] ?? '') ?></small></span></a>
        <span class="lg-played"><?= (int)$r['played'] ?> <?= $r['played'] === 1 ? 'round' : 'rounds' ?></span><span class="lg-pts"><?= lg_h(number_format((float)$r['average'], 2)) ?></span></li>
      <?php endforeach ?>
    </ol>
    <?php else: ?>
    <p class="lg-empty">No club has <?= LG_CLUB_TABLE_MIN ?> rounds <?= $p === 'today' ? 'today' : ($p === 'week' ? 'this week' : '') ?> yet. Play your club’s Daily Five and get your mates to play too.</p>
    <?php endif ?>
    <?php $waiting = array_filter($t['unranked'], fn($r) => $r['played'] > 0); if ($waiting): ?>
    <p class="lg-waiting">Not enough players yet (<?= LG_CLUB_TABLE_MIN ?> needed): <?= implode('', array_map(fn($r) => '<span data-league="' . lg_h($r['league']) . '"><a href="/daily-five/' . lg_h($r['slug']) . '">' . lg_h($r['name']) . '</a> (' . (int)$r['played'] . ')</span>', $waiting)) ?></p>
    <?php endif ?>
  </div>
  <?php $first = false; endforeach ?>
  <p class="lg-note">Score = average out of 5 across every finished round of that club’s Daily Five. A club needs at least <?= LG_CLUB_TABLE_MIN ?> rounds to get a position. Weeks run Monday to Sunday. No names or accounts are involved: every round counts.</p>
</section>

<section class="lg-card">
  <h2>Derby days</h2>
  <?php $t = $tables['week']['by_slug']; $derbies = array_filter($rivalPairs, fn($p) => ($t[$p[0]]['played'] ?? 0) + ($t[$p[1]]['played'] ?? 0) > 0); ?>
  <?php if (!$derbies): ?><p class="lg-empty">No derby has been played this week yet. Arsenal v Spurs, Forest v Derby, Cardiff v Swansea… whose fans will start it?</p><?php endif ?>
  <ul class="lg-derbies">
  <?php foreach ($derbies as [$a, $b]): $x = $t[$a]; $y = $t[$b]; ?>
    <li><a href="/daily-five/<?= lg_h($a) ?>"><?= lg_h($x['name']) ?></a> <b><?= $x['played'] ? lg_h(number_format((float)$x['average'], 1)) : '–' ?></b> <span>v</span> <b><?= $y['played'] ? lg_h(number_format((float)$y['average'], 1)) : '–' ?></b> <a href="/daily-five/<?= lg_h($b) ?>"><?= lg_h($y['name']) ?></a></li>
  <?php endforeach ?>
  </ul>
  <?php if ($derbies): ?><p class="lg-note">This week’s average scores for rival clubs that have been played. – means nobody has played that club yet this week.</p><?php endif ?>
</section>

<section class="lg-card lg-cta"><h2>Help your club up the table</h2><p>Every round counts, so the more of your club’s fans play, the better your chances. Share your score after you play, or start a private league with your mates.</p><div class="lg-actions"><a class="lg-button primary" href="/daily-football-quiz">Play the Daily Five</a><a class="lg-button" href="/leagues">Private leagues</a></div></section>
<?php lg_page_foot();
