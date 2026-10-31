<?php
// Sends Daily Five reminders. Run every 15 minutes as www-data (systemd timer clubdailyfive-reminders).
// Each device gets at most one reminder a day, at the time it chose, and none on a day it has already played.
// Usage: send_reminders.php            normal run
//        send_reminders.php --dry-run  show who would get what, send nothing
declare(strict_types=1);
require '/var/www/clubdailyfive.com/public_html/push-lib.php';

$dry = in_array('--dry-run', $argv, true);
if (!push_ready()) { fwrite(STDERR, "Push keys missing\n"); exit(1); }
$db = push_db();
$today = lg_today();
$now = date('H:i');
$sent = $failed = $removed = $skipped = 0;

// Clubs whose round for today is published (a reminder for a missing round would disappoint).
$ready = [];
$q = lg_quiz_db()->prepare('SELECT c.slug FROM daily_questions d JOIN clubs c ON c.id=d.club_id WHERE d.quiz_date=? GROUP BY c.id HAVING COUNT(*)=5');
$q->execute([$today]);
foreach ($q->fetchAll(PDO::FETCH_COLUMN) as $slug) $ready[$slug] = true;

foreach (PUSH_SLOTS as $slot => [$time, $label]) {
    // Due from the slot time; give up after 3 hours (e.g. after server downtime) rather than remind late in the day.
    $due = strtotime("$today $time"); $nowTs = time();
    if ($nowTs < $due || $nowTs > $due + 3 * 3600) continue;
    $s = $db->prepare('SELECT * FROM push_subs WHERE slot=? AND (last_sent IS NULL OR last_sent<?) AND (last_played IS NULL OR last_played<?)');
    $s->execute([$slot, $today, $today]);
    foreach ($s->fetchAll() as $sub) {
        if (!isset($ready[$sub['club_slug']]) || !push_known_host((string)parse_url($sub['endpoint'], PHP_URL_HOST))) { $skipped++; continue; }
        $msg = push_message($sub);
        if ($dry) { echo "[$slot] {$sub['club_slug']}: {$msg['title']} / {$msg['body']}\n"; continue; }
        $db->prepare('UPDATE push_subs SET last_sent=? WHERE endpoint=?')->execute([$today, $sub['endpoint']]);
        try { $status = push_send_one($sub, $msg, 'daily-five'); }
        catch (Throwable $e) { error_log('ClubDailyFive push: ' . $e->getMessage()); $failed++; continue; }
        if ($status === 404 || $status === 410) {
            $db->prepare('DELETE FROM push_subs WHERE endpoint=?')->execute([$sub['endpoint']]); $removed++;
        } elseif ($status >= 200 && $status < 300) {
            $db->prepare('UPDATE push_subs SET last_ok=? WHERE endpoint=?')->execute([time(), $sub['endpoint']]); $sent++;
        } else {
            $failed++;
        }
    }
}
$total = (int)$db->query('SELECT COUNT(*) FROM push_subs')->fetchColumn();
if ($sent || $failed || $removed || $dry) echo date('c') . " reminders: sent $sent, failed $failed, expired removed $removed, skipped $skipped; $total devices signed up\n";
