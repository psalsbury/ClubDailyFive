<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
function h(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8'); }
$qdb=new PDO('sqlite:/var/lib/predictioncomp/clubquiz.sqlite',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$adb=new PDO('sqlite:/var/lib/predictioncomp/analytics.sqlite',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$udb=new PDO('sqlite:/var/lib/predictioncomp/api_football_quota.sqlite',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$clubs=$qdb->query("SELECT c.slug,c.name,
 COUNT(q.id) questions,
 SUM(CASE WHEN q.use_count>0 THEN 1 ELSE 0 END) questions_used,
 COALESCE(SUM(q.use_count),0) total_uses,
 MAX(CASE WHEN q.semantic_key LIKE 'v4bank|%' THEN q.created_at END) replenished
 FROM clubs c LEFT JOIN questions q ON q.club_id=c.id
 WHERE c.active=1 GROUP BY c.id ORDER BY c.name")->fetchAll(PDO::FETCH_ASSOC);
$analytics=[];
foreach($adb->query("SELECT club_slug,
 COUNT(DISTINCT CASE WHEN event_type='started' THEN player_id END) players_started,
 COUNT(DISTINCT CASE WHEN event_type='completed' THEN player_id END) players_completed,
 COUNT(CASE WHEN event_type='selected' THEN 1 END) selections
 FROM player_events GROUP BY club_slug") as $r) $analytics[$r['club_slug']]=$r;
$uniqueStarted=(int)$adb->query("SELECT COUNT(DISTINCT player_id) FROM player_events WHERE event_type='started'")->fetchColumn();
$uniqueCompleted=(int)$adb->query("SELECT COUNT(DISTINCT player_id) FROM player_events WHERE event_type='completed'")->fetchColumn();
$totalCompletions=(int)$adb->query("SELECT COUNT(*) FROM player_events WHERE event_type='completed'")->fetchColumn();
$players=$adb->query("SELECT player_id,
 MIN(created_at) first_seen,MAX(created_at) last_seen,
 GROUP_CONCAT(DISTINCT club_slug) clubs,
 COUNT(DISTINCT CASE WHEN event_type='started' THEN event_date||'|'||club_slug END) rounds_started,
 COUNT(DISTINCT CASE WHEN event_type='completed' THEN event_date||'|'||club_slug END) rounds_completed
 FROM player_events GROUP BY player_id ORDER BY last_seen DESC")->fetchAll(PDO::FETCH_ASSOC);
$usage=[];
$stmt=$udb->prepare("SELECT calls FROM api_football_daily_usage WHERE utc_day=?");
for($i=6;$i>=0;$i--){$d=(new DateTimeImmutable('today',new DateTimeZone('UTC')))->modify("-$i days")->format('Y-m-d');$stmt->execute([$d]);$usage[$d]=(int)($stmt->fetchColumn()?:0);}
$replenishmentDates=array_filter(array_column($clubs,'replenished'));
$lastReplenish=$replenishmentDates ? max($replenishmentDates) : 'Not recorded';
?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#07101e"><title>Owner statistics — ClubDailyFive.com</title>
<style>
:root{--bg:#07101e;--panel:#111c31;--line:#273650;--ink:#f7f8fc;--muted:#a9b2c4;--teal:#13d7c5;--lime:#a9ed36}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,rgba(19,215,197,.13),transparent 34rem),var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif}.wrap{width:min(1180px,calc(100% - 28px));margin:auto;padding:24px 0 60px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:28px}.logo{width:min(330px,58vw)}.badge{color:var(--teal);font-size:.75rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}h1{font-size:clamp(2.1rem,6vw,4.3rem);letter-spacing:-.06em;margin:.1em 0 .5em}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 32px}.card{padding:20px;border:1px solid var(--line);border-radius:16px;background:rgba(17,28,49,.88)}.value{display:block;font-size:2rem;font-weight:950;color:var(--teal)}.label{color:var(--muted);font-size:.8rem}.section{margin-top:32px}.section h2{font-size:1.2rem;margin:0 0 12px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:16px;background:var(--panel)}table{width:100%;border-collapse:collapse;min-width:760px}th,td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em}td{font-size:.88rem}tr:last-child td{border:0}.num{text-align:right}.api{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}.api-day{padding:14px 6px;text-align:center;border:1px solid var(--line);border-radius:13px;background:var(--panel)}.api-day b{display:block;color:var(--teal);font-size:1.5rem}.api-day span{color:var(--muted);font-size:.68rem}.note{color:var(--muted);font-size:.8rem;line-height:1.5;margin-top:10px}@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}.api{grid-template-columns:repeat(4,1fr)}.top{align-items:flex-start;flex-direction:column}.wrap{padding-top:16px}}
</style></head><body><main class="wrap">
<div class="top"><img class="logo" src="/assets/clubdailyfive-logo.svg" alt="ClubDailyFive.com"><span class="badge">Private owner dashboard</span></div>
<h1>Site statistics</h1>
<section class="cards">
<div class="card"><span class="value"><?=h($uniqueStarted)?></span><span class="label">Unique players started</span></div>
<div class="card"><span class="value"><?=h($uniqueCompleted)?></span><span class="label">Unique players completed</span></div>
<div class="card"><span class="value"><?=h($totalCompletions)?></span><span class="label">Total completed rounds</span></div>
<div class="card"><span class="value"><?=h($lastReplenish)?></span><span class="label">Last question replenishment</span></div>
</section>
<section class="section"><h2>API-Football calls — last seven UTC days</h2><div class="api"><?php foreach($usage as $d=>$calls): ?><div class="api-day"><b><?=h($calls)?></b><span><?=h((new DateTimeImmutable($d))->format('D j M'))?></span></div><?php endforeach ?></div></section>
<section class="section"><h2>Question bank and players by club</h2><div class="table-wrap"><table><thead><tr><th>Club</th><th class="num">Questions</th><th class="num">Questions used</th><th class="num">Total uses</th><th>Last replenished</th><th class="num">Players</th><th class="num">Completed</th><th class="num">Selections</th></tr></thead><tbody>
<?php foreach($clubs as $c): $a=$analytics[$c['slug']]??[]; ?><tr><td><strong><?=h($c['name'])?></strong></td><td class="num"><?=h($c['questions'])?></td><td class="num"><?=h($c['questions_used'])?></td><td class="num"><?=h($c['total_uses'])?></td><td><?=h($c['replenished']?:'—')?></td><td class="num"><?=h($a['players_started']??0)?></td><td class="num"><?=h($a['players_completed']??0)?></td><td class="num"><?=h($a['selections']??0)?></td></tr><?php endforeach ?>
</tbody></table></div></section>
<section class="section"><h2>Anonymous player club breakdown</h2><div class="table-wrap"><table><thead><tr><th>Anonymous player</th><th>Clubs selected</th><th class="num">Rounds started</th><th class="num">Rounds completed</th><th>First seen</th><th>Last seen</th></tr></thead><tbody>
<?php if(!$players): ?><tr><td colspan="6">Player tracking begins from this dashboard’s deployment.</td></tr><?php endif; foreach($players as $p): ?><tr><td><?=h(substr($p['player_id'],0,12))?>…</td><td><?=h(str_replace(',',', ',$p['clubs']))?></td><td class="num"><?=h($p['rounds_started'])?></td><td class="num"><?=h($p['rounds_completed'])?></td><td><?=h($p['first_seen'])?></td><td><?=h($p['last_seen'])?></td></tr><?php endforeach ?>
</tbody></table></div><p class="note">Players are identified by a random browser ID. No names, email addresses or IP addresses are stored.</p></section>
</main></body></html>