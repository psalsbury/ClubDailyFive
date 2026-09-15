<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
header('Cache-Control: no-store');
function h(mixed $value): string { return htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8'); }
$today = new DateTimeImmutable('today');
$day = $today->format('Y-m-d');
$week = $today->modify('monday this week')->format('Y-m-d');
$month = $today->format('Y-m-01');
$options = [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION];
$qdb = new PDO('sqlite:/var/lib/clubdailyfive/clubquiz.sqlite', null, null, $options);
$clubs = $qdb->query('SELECT slug,name FROM clubs WHERE active=1 ORDER BY name')->fetchAll(PDO::FETCH_ASSOC);
$adb = new PDO('sqlite:/var/lib/clubdailyfive/analytics.sqlite', null, null, $options);
$adb->exec('PRAGMA busy_timeout=3000');
$stmt = $adb->prepare('SELECT club_slug,
 SUM(CASE WHEN event_date=:day THEN started ELSE 0 END) day_started,
 SUM(CASE WHEN event_date=:day THEN completed ELSE 0 END) day_completed,
 SUM(CASE WHEN event_date>=:week THEN started ELSE 0 END) week_started,
 SUM(CASE WHEN event_date>=:week THEN completed ELSE 0 END) week_completed,
 SUM(CASE WHEN event_date>=:month THEN started ELSE 0 END) month_started,
 SUM(CASE WHEN event_date>=:month THEN completed ELSE 0 END) month_completed
 FROM club_daily_totals WHERE event_date>=:earliest AND event_date<=:day GROUP BY club_slug');
$stmt->execute([':day'=>$day, ':week'=>$week, ':month'=>$month, ':earliest'=>min($week,$month)]);
$counts = $stmt->fetchAll(PDO::FETCH_UNIQUE|PDO::FETCH_ASSOC);
$columns = ['day_started','day_completed','week_started','week_completed','month_started','month_completed'];
$totals = array_fill_keys($columns, 0);
foreach ($clubs as $club) foreach ($columns as $column) $totals[$column] += (int)($counts[$club['slug']][$column] ?? 0);
?>
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Owner statistics — ClubDailyFive</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#07101e;color:#f7f8fc;font:16px system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:28px 16px}h1{margin:12px 0}a{color:#13d7c5}p{color:#a9b2c4;line-height:1.5}.table-wrap{overflow:auto;border:1px solid #273650;border-radius:12px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:12px;border-bottom:1px solid #273650;text-align:right;white-space:nowrap}th:first-child{text-align:left}thead{background:#111c31}thead th{text-align:center}tbody th{font-weight:500}tfoot{font-weight:bold;background:#111c31}.note{font-size:.875rem}
</style></head><body><main>
<a href="/">ClubDailyFive.com</a><h1>Round activity</h1>
<p>Today: <?=h($today->format('j F Y'))?> · Week from <?=h((new DateTimeImmutable($week))->format('j F'))?> · Month: <?=h($today->format('F Y'))?>. All dates use UK time.</p>
<div class="table-wrap"><table><thead><tr><th rowspan="2" scope="col">Club</th><th colspan="2" scope="colgroup">Today</th><th colspan="2" scope="colgroup">This week</th><th colspan="2" scope="colgroup">This month</th></tr><tr><?php for($i=0;$i<3;$i++): ?><th scope="col">Started</th><th scope="col">Completed</th><?php endfor; ?></tr></thead><tbody>
<?php foreach($clubs as $club): ?><tr><th scope="row"><?=h($club['name'])?></th><?php foreach($columns as $column): ?><td><?=h($counts[$club['slug']][$column]??0)?></td><?php endforeach; ?></tr><?php endforeach; ?>
</tbody><tfoot><tr><th scope="row">All clubs</th><?php foreach($columns as $column): ?><td><?=h($totals[$column])?></td><?php endforeach; ?></tr></tfoot></table></div>
<p class="note">Counts are round starts and completions, not unique people across days or clubs. A player returning on another day counts again. Only daily club totals are stored; there are no individual player records. Weeks begin on Monday.</p>
</main></body></html>
