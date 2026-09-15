<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo '{"ok":false}'; exit; }
$origin = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
if ($origin !== '' && !preg_match('#^https://(www\.)?clubdailyfive\.com$#i', $origin)) { http_response_code(403); echo '{"ok":false}'; exit; }
$data = json_decode((string)file_get_contents('php://input'), true);
$player = (string)($data['player_id'] ?? '');
$club = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($data['club'] ?? '')));
$event = (string)($data['event'] ?? '');
if (!preg_match('/^[a-zA-Z0-9_-]{16,64}$/', $player) || !in_array($event, ['selected','started','completed'], true) || $club === '') {
    http_response_code(422); echo '{"ok":false}'; exit;
}
$quiz = new PDO('sqlite:/var/lib/clubdailyfive/clubquiz.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$check = $quiz->prepare('SELECT 1 FROM clubs WHERE slug=? AND active=1');
$check->execute([$club]);
if (!$check->fetchColumn()) { http_response_code(422); echo '{"ok":false}'; exit; }
$db = new PDO('sqlite:/var/lib/clubdailyfive/analytics.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$db->exec('PRAGMA busy_timeout=3000');
$stmt = $db->prepare('INSERT OR IGNORE INTO player_events(player_id,club_slug,event_type,event_date) VALUES(?,?,?,?)');
$stmt->execute([$player,$club,$event,(new DateTimeImmutable('now',new DateTimeZone('Europe/London')))->format('Y-m-d')]);
echo '{"ok":true}';
