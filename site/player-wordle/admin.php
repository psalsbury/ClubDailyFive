<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('X-Robots-Tag: noindex, nofollow', true);

function h(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8');
}

$today = new DateTimeImmutable('today');
$day = $today->format('Y-m-d');
$week = $today->modify('monday this week')->format('Y-m-d');
$month = $today->format('Y-m-01');
$earliest = min($week, $month);

$db = new PDO(
    'sqlite:/var/lib/clubdailyfive/player-wordle/game.sqlite3',
    null,
    null,
    [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
);
$db->exec('PRAGMA busy_timeout=3000');

$clubs = $db->query('SELECT id, name FROM clubs WHERE active=1 ORDER BY name')->fetchAll(PDO::FETCH_ASSOC);
$stmt = $db->prepare(
    'SELECT club_id,
      SUM(CASE WHEN stat_date=:day THEN started ELSE 0 END) day_started,
      SUM(CASE WHEN stat_date=:day THEN completed ELSE 0 END) day_completed,
      SUM(CASE WHEN stat_date=:day THEN won ELSE 0 END) day_won,
      SUM(CASE WHEN stat_date>=:week THEN started ELSE 0 END) week_started,
      SUM(CASE WHEN stat_date>=:week THEN completed ELSE 0 END) week_completed,
      SUM(CASE WHEN stat_date>=:week THEN won ELSE 0 END) week_won,
      SUM(CASE WHEN stat_date>=:month THEN started ELSE 0 END) month_started,
      SUM(CASE WHEN stat_date>=:month THEN completed ELSE 0 END) month_completed,
      SUM(CASE WHEN stat_date>=:month THEN won ELSE 0 END) month_won
     FROM aggregate_stats
     WHERE stat_date>=:earliest AND stat_date<=:day
     GROUP BY club_id'
);
$stmt->execute([':day'=>$day, ':week'=>$week, ':month'=>$month, ':earliest'=>$earliest]);
$counts = $stmt->fetchAll(PDO::FETCH_UNIQUE | PDO::FETCH_ASSOC);
$periods = [
    'day' => ['Today', $today->format('j F Y')],
    'week' => ['This week', 'From '.(new DateTimeImmutable($week))->format('j F Y')],
    'month' => ['This month', $today->format('F Y')],
];
$totals = [];
foreach (array_keys($periods) as $period) {
    $totals[$period] = ['started'=>0, 'completed'=>0, 'won'=>0];
}
foreach ($clubs as $club) {
    $row = $counts[$club['id']] ?? [];
    foreach (array_keys($periods) as $period) {
        foreach (['started','completed','won'] as $metric) {
            $totals[$period][$metric] += (int)($row[$period.'_'.$metric] ?? 0);
        }
    }
}
function percent(int $part, int $whole): string {
    return $whole > 0 ? number_format(($part / $whole) * 100, 1).'%' : '—';
}
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Player Wordle Admin</title>
<style>
:root{color-scheme:dark;--bg:#07101e;--panel:#101f31;--line:#28384d;--muted:#a9b2c4;--green:#22c55e;--cyan:#20d9d0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:#f7f8fc;font:16px system-ui,-apple-system,sans-serif}
main{max-width:1200px;margin:auto;padding:24px 16px 40px}
a{color:var(--cyan);text-decoration:none}.eyebrow{color:var(--cyan);font-size:.78rem;font-weight:800;letter-spacing:.14em}
h1{margin:.35rem 0 .25rem;font-size:clamp(1.8rem,5vw,2.6rem)}p{color:var(--muted);line-height:1.5}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}.card small{display:block;color:var(--muted)}.card strong{display:block;font-size:1.8rem;margin:5px 0}.card span{color:var(--green);font-size:.85rem}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child{text-align:left;position:sticky;left:0;background:var(--panel)}
thead{background:#14243a}thead th{text-align:center}thead th:first-child{background:#14243a}
tbody th{font-weight:600}tfoot{font-weight:800;background:#14243a}tfoot th:first-child{background:#14243a}
.note{font-size:.875rem}.zero{color:#667085}
@media(max-width:700px){main{padding:16px 10px 30px}.cards{grid-template-columns:1fr}.card{display:grid;grid-template-columns:1fr auto;align-items:center}.card strong{grid-row:1/3;grid-column:2}.card span{grid-column:1}.table-wrap{font-size:.82rem}th,td{padding:9px 8px}}
</style>
</head>
<body><main>
<a href="./">← Player Wordle</a>
<div class="eyebrow">PASSWORD-PROTECTED OWNER VIEW</div>
<h1>Site usage</h1>
<p>Aggregate game activity in UK time. No names, accounts, IP addresses or individual-player histories are stored.</p>
<div class="cards">
<?php foreach ($periods as $key=>$period): ?>
<section class="card"><small><?=h($period[0])?> · <?=h($period[1])?></small><strong><?=number_format($totals[$key]['started'])?></strong><span><?=number_format($totals[$key]['completed'])?> completed · <?=percent($totals[$key]['completed'],$totals[$key]['started'])?></span></section>
<?php endforeach; ?>
</div>
<div class="table-wrap"><table>
<thead><tr><th rowspan="2" scope="col">Club</th><?php foreach ($periods as $period): ?><th colspan="4" scope="colgroup"><?=h($period[0])?></th><?php endforeach; ?></tr>
<tr><?php for($i=0;$i<3;$i++): ?><th>Started</th><th>Completed</th><th>Won</th><th>Win rate</th><?php endfor; ?></tr></thead>
<tbody>
<?php foreach ($clubs as $club): $row=$counts[$club['id']]??[]; ?><tr><th scope="row"><?=h($club['name'])?></th>
<?php foreach (array_keys($periods) as $period): $started=(int)($row[$period.'_started']??0);$completed=(int)($row[$period.'_completed']??0);$won=(int)($row[$period.'_won']??0); ?>
<td class="<?=$started===0?'zero':''?>"><?=number_format($started)?></td><td><?=number_format($completed)?></td><td><?=number_format($won)?></td><td><?=percent($won,$completed)?></td>
<?php endforeach; ?></tr><?php endforeach; ?>
</tbody>
<tfoot><tr><th scope="row">All clubs</th><?php foreach (array_keys($periods) as $period): ?><td><?=number_format($totals[$period]['started'])?></td><td><?=number_format($totals[$period]['completed'])?></td><td><?=number_format($totals[$period]['won'])?></td><td><?=percent($totals[$period]['won'],$totals[$period]['completed'])?></td><?php endforeach; ?></tr></tfoot>
</table></div>
<p class="note">A start is recorded when a club game page opens; a completion is recorded when the round ends. Refreshes may increase starts, so these figures describe game activity rather than unique people. Weeks begin on Monday.</p>
</main></body></html>
