<?php
declare(strict_types=1);date_default_timezone_set('Europe/London');
header('Content-Type: application/json');header('Cache-Control: no-store');
if($_SERVER['REQUEST_METHOD']!=='POST'){http_response_code(405);exit('{}');}
if((int)($_SERVER['CONTENT_LENGTH']??0)>2048){http_response_code(413);exit('{}');}
$data=json_decode(file_get_contents('php://input'),true);$event=$data['event']??'';
if(!is_string($event)||!in_array($event,["guess_1", "guess_2", "guess_3", "guess_4", "guess_5", "page_open", "typing", "input_focus", "suggestions_shown", "no_suggestions", "guess_selected", "guess_accepted", "completed", "restored_completed", "restored_in_progress", "tutorial_offered", "tutorial_opened", "tutorial_completed", "tutorial_closed", "tutorial_dismissed", "storage_error", "javascript_error", "promise_error", "api_suggest_error", "api_guess_error", "api_finish_error", "api_start_error", "api_answer_error", "tutorial_step_1", "tutorial_step_2", "tutorial_step_3", "tutorial_step_4", "tutorial_step_5", "left_after_0_guesses", "left_after_1_guesses", "left_after_2_guesses", "left_after_3_guesses", "left_after_4_guesses", "left_after_5_guesses"],true)){http_response_code(400);exit('{}');}
try{
$db=new PDO('sqlite:/var/lib/clubdailyfive/player-wordle/game.sqlite3');$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);$db->exec('PRAGMA busy_timeout=5000');
$q=$db->prepare('SELECT id FROM clubs WHERE slug=? AND active=1');$q->execute([substr((string)($data['club']??''),0,80)]);$cid=$q->fetchColumn();$q->closeCursor();if(!$cid){http_response_code(400);exit('{}');}
$db->exec('CREATE TABLE IF NOT EXISTS diagnostic_counts(stat_date TEXT NOT NULL,club_id INTEGER NOT NULL,event TEXT NOT NULL,total INTEGER NOT NULL,last_seen TEXT NOT NULL,PRIMARY KEY(stat_date,club_id,event))');
$db->prepare('INSERT INTO diagnostic_counts VALUES(?,?,?,1,?) ON CONFLICT(stat_date,club_id,event) DO UPDATE SET total=total+1,last_seen=excluded.last_seen')->execute([date('Y-m-d'),$cid,$event,date('H:i:s')]);
$db->prepare('DELETE FROM diagnostic_counts WHERE stat_date<?')->execute([date('Y-m-d',strtotime('-30 days'))]);echo '{"ok":true}';
}catch(Throwable $e){http_response_code(503);echo '{}';}
