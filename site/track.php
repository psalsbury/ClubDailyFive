<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo '{"ok":false}'; exit; }
$origin = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
if ($origin !== '' && !preg_match('#^https://(www\.)?clubdailyfive\.com$#i', $origin)) { http_response_code(403); echo '{"ok":false}'; exit; }
$data = json_decode((string)file_get_contents('php://input'), true);
$club = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($data['club'] ?? '')));
$event = (string)($data['event'] ?? '');
if (!in_array($event, ['selected','started','completed','shown'], true) || $club === '') {
    http_response_code(422); echo '{"ok":false}'; exit;
}
$quiz = new PDO('sqlite:/var/lib/clubdailyfive/clubquiz.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$check = $quiz->prepare('SELECT id FROM clubs WHERE slug=? AND active=1');
$check->execute([$club]);
if (!($clubId = $check->fetchColumn())) { http_response_code(422); echo '{"ok":false}'; exit; }
// Count a question at most once per UK day, regardless of refreshes/players.
// Publication alone never consumes a question.
if ($event === 'shown') {
    $qid = filter_var($data['question_id'] ?? null, FILTER_VALIDATE_INT);
    $roundDate = (string)($data['quiz_date'] ?? '');
    $today = (new DateTimeImmutable('now'))->format('Y-m-d');
    if (!$qid || !preg_match('/^\d{4}-\d{2}-\d{2}$/', $roundDate) || $roundDate > $today) {
        http_response_code(422); echo '{"ok":false}'; exit;
    }
    $quiz->exec('PRAGMA busy_timeout=4000');
    $quiz->exec('BEGIN IMMEDIATE');
    try {
        $valid = $quiz->prepare('SELECT 1 FROM daily_questions WHERE club_id=? AND quiz_date=? AND question_id=?');
        $valid->execute([$clubId, $roundDate, $qid]);
        if (!$valid->fetchColumn()) {
            $quiz->exec('ROLLBACK'); http_response_code(422); echo '{"ok":false}'; exit;
        }
        $insert = $quiz->prepare('INSERT OR IGNORE INTO question_play_days(question_id,play_date) VALUES(?,?)');
        $insert->execute([$qid, $today]);
        if ($insert->rowCount() === 1) {
            $update = $quiz->prepare('UPDATE questions SET use_count=use_count+1,last_used_date=? WHERE id=?');
            $update->execute([$today, $qid]);
        }
        $quiz->exec('COMMIT');
    } catch (Throwable $e) {
        $quiz->exec('ROLLBACK'); throw $e;
    }
    echo '{"ok":true}'; exit;
}
// Ignore legacy page events. No identity is accepted or persisted.
if (!in_array($event, ['started','completed'], true) || ($data['analytics_version'] ?? null) !== 2) {
    echo '{"ok":true}'; exit;
}
$today = new DateTimeImmutable('today');
if (($data['play_date'] ?? '') !== $today->format('Y-m-d')) {
    http_response_code(422); echo '{"ok":false}'; exit;
}
$weekStart = $today->modify('monday this week')->format('Y-m-d');
$monthStart = $today->format('Y-m-01');
$retainFrom = min($weekStart, $monthStart);
$db = new PDO('sqlite:/var/lib/clubdailyfive/analytics.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$db->exec('PRAGMA busy_timeout=3000');
$db->beginTransaction();
try {
    $stmt = $db->prepare('INSERT INTO club_daily_totals(event_date,club_slug,started,completed) VALUES(?,?,?,?)
        ON CONFLICT(event_date,club_slug) DO UPDATE SET started=started+excluded.started,completed=completed+excluded.completed');
    $stmt->execute([$today->format('Y-m-d'), $club, $event === 'started' ? 1 : 0, $event === 'completed' ? 1 : 0]);
    $prune = $db->prepare('DELETE FROM club_daily_totals WHERE event_date<?');
    $prune->execute([$retainFrom]);
    $db->commit();
} catch (Throwable $e) {
    $db->rollBack(); throw $e;
}
echo '{"ok":true}';
