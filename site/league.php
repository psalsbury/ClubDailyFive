<?php
// /league/<CODE>: one private league.  /leagues: your name, your leagues, create or join.
declare(strict_types=1);
require __DIR__ . '/leagues-lib.php';
header('Cache-Control: no-store');

$clubsJson = json_encode(array_values(array_map(fn($c) => ['slug' => $c['slug'], 'name' => $c['name'], 'league' => $c['league']], lg_clubs())), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
$code = (string)($_GET['code'] ?? '');

if ($code === '') {
    lg_page_head('Private Football Quiz Leagues – Daily Five | ClubDailyFive', 'Start a private Daily Five league for your mates, share the link and see who knows their club best.');
    ?>
<section class="lg-hero"><div><div class="eyebrow">Daily Five</div><h1>Private leagues</h1><p class="lg-lede">Play the Daily Five for your club, then compare scores with your mates. Each friend plays their own club’s quiz. The table shows today, this week (Monday to Sunday) and all time.</p></div></section>
<div class="lg-setup" data-setup></div>
<section class="lg-card" data-my-leagues hidden><h2>Your leagues</h2><ul class="lg-league-list" data-league-list></ul></section>
<section class="lg-card" data-create hidden>
  <h2>Start a league</h2>
  <form class="lg-form" data-create-form><label>League name<input name="name" maxlength="32" required placeholder="e.g. The Five-a-side Lads" autocomplete="off"></label><button class="lg-button primary">Create league</button><p class="lg-msg" role="status"></p></form>
</section>
<section class="lg-card" data-join hidden>
  <h2>Join with a code</h2>
  <form class="lg-form lg-inline" data-join-form><label>League code<input name="code" maxlength="6" required placeholder="ABC234" autocomplete="off" autocapitalize="characters"></label><button class="lg-button">Join</button><p class="lg-msg" role="status"></p></form>
</section>
<section class="lg-card"><h2>Club fan tables</h2><p>Every club also has a public table of its named fans.</p><nav class="lg-other"><?php foreach (lg_clubs() as $c): ?><a href="/fans/<?= lg_h($c['slug']) ?>"><?= lg_h($c['name']) ?></a><?php endforeach ?></nav></section>
<script>window.CDF_CLUBS=<?= $clubsJson ?>;</script>
<?php
    lg_page_foot();
    exit;
}

$league = lg_league_by_code($code);
if (!$league) {
    http_response_code(404);
    lg_page_head('League not found | ClubDailyFive', 'This private league link is not valid.');
    echo '<section class="lg-card"><h1>League not found</h1><p>Check the link or code with whoever sent it.</p><a class="lg-button primary" href="/leagues">Private leagues</a></section>';
    lg_page_foot();
    exit;
}
if ($code !== $league['code']) { header('Location: /league/' . $league['code'], true, 301); exit; }

$id = (int)$league['id'];
$inLeague = 'p.id IN (SELECT player_id FROM league_members WHERE league_id=?)';
$tables = [];
foreach (['today', 'week', 'all'] as $p) $tables[$p] = lg_table($p, $inLeague, [$id], 300);
$members = lg_league_members($id);
$playedToday = array_flip(array_column($tables['today'], 'public_id'));
$waiting = array_values(array_filter($members, fn($m) => !isset($playedToday[$m['public_id']])));
$url = 'https://clubdailyfive.com/league/' . $league['code'];
$count = count($members);

lg_page_head($league['name'] . ' – Daily Five League | ClubDailyFive', 'Join ' . $league['name'] . ' on ClubDailyFive: five questions on your club every day, one league table for your mates.');
?>
<section class="lg-hero"><div><div class="eyebrow">Private league · <?= $count ?> <?= $count === 1 ? 'member' : 'members' ?></div><h1><?= lg_h($league['name']) ?></h1></div></section>

<section class="lg-card lg-invite" data-league-code="<?= lg_h($league['code']) ?>" data-league-name="<?= lg_h($league['name']) ?>">
  <div data-join-box hidden>
    <p class="lg-lede">You’ve been invited. Pick a name and your club to join.</p>
    <div class="lg-setup" data-setup data-join-code="<?= lg_h($league['code']) ?>"></div>
  </div>
  <div data-member-box hidden>
    <p class="lg-lede" data-member-line></p>
    <div class="lg-actions"><a class="lg-button primary" data-play-link href="/daily-football-quiz">Play today’s Daily Five</a><button class="lg-button" data-invite type="button">Invite friends</button></div>
  </div>
  <div data-joinable hidden><button class="lg-button primary" data-join-now type="button">Join this league</button></div>
  <p class="lg-code">League code <b><?= lg_h($league['code']) ?></b> · <span class="lg-url"><?= lg_h($url) ?></span></p>
  <p class="lg-msg" role="status" data-invite-status></p>
</section>

<section class="lg-card">
  <div class="lg-tabs" role="tablist">
    <button role="tab" aria-selected="true" data-tab="today">Today</button><button role="tab" aria-selected="false" data-tab="week">This week</button><button role="tab" aria-selected="false" data-tab="all">All time</button>
  </div>
  <div data-panel="today"><?php lg_render_table($tables['today'], 'today', true, 'Nobody has played today yet.') ?>
    <?php if ($waiting && $tables['today']): ?><p class="lg-waiting">Yet to play: <?= lg_h(implode(', ', array_column($waiting, 'name'))) ?></p><?php endif ?></div>
  <div data-panel="week" hidden><?php lg_render_table($tables['week'], 'week', true, 'No rounds this week yet. Weeks run Monday to Sunday.') ?></div>
  <div data-panel="all" hidden><?php lg_render_table($tables['all'], 'all', true, 'No rounds yet.') ?></div>
  <p class="lg-note">One round a day counts: the Daily Five for each player’s own club. Rounds played before someone joined still count.</p>
  <p class="lg-leave" data-leave-box hidden><button type="button" class="lg-link" data-leave>Leave this league</button></p>
</section>
<script>window.CDF_CLUBS=<?= $clubsJson ?>;</script>
<?php lg_page_foot();
