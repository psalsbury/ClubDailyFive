<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');
header('Content-Type: application/json'); header('Cache-Control: no-store');
function respond(int $status,bool $ok): never {http_response_code($status);echo json_encode(['ok'=>$ok]);exit;}
if($_SERVER['REQUEST_METHOD']!=='POST')respond(405,false);
if(!preg_match('#^https://(www\.)?clubdailyfive\.com$#i',$_SERVER['HTTP_ORIGIN']??''))respond(403,false);
if((int)($_SERVER['CONTENT_LENGTH']??0)>2048)respond(413,false);
$d=json_decode(file_get_contents('php://input'),true);
if(!is_array($d))respond(422,false);
$club=(string)($d['club']??'');$event=(string)($d['event']??'');$game=(string)($d['game']??'daily');
$q=new PDO('sqlite:/var/lib/clubdailyfive/clubquiz.sqlite',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);$q->exec('PRAGMA busy_timeout=3000');
$c=$q->prepare('SELECT id FROM clubs WHERE slug=? AND active=1');$c->execute([$club]);$cid=$c->fetchColumn();if(!$cid)respond(422,false);
$a=new PDO('sqlite:/var/lib/clubdailyfive/analytics.sqlite',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);$a->exec('PRAGMA busy_timeout=3000');
if($event==='report'){
 $reason=(string)($d['reason']??'');$qid=filter_var($d['question_id']??null,FILTER_VALIDATE_INT);$date=(string)($d['quiz_date']??'');
 if(!in_array($reason,['incorrect','outdated','repeated'],true)||!$qid)respond(422,false);
 $v=$q->prepare('SELECT 1 FROM daily_questions WHERE club_id=? AND quiz_date=? AND question_id=?');$v->execute([$cid,$date,$qid]);if(!$v->fetchColumn())respond(422,false);
 $s=$a->prepare('INSERT OR IGNORE INTO question_reports(question_id,club_slug,quiz_date,reason) VALUES(?,?,?,?)');$s->execute([$qid,$club,$date,$reason]);
 if($s->rowCount()===1){
  $reportId=(int)$a->lastInsertId();
  try{
   require_once __DIR__.'/report-notification.php';
   $detail=$q->prepare('SELECT question_text,options_json,correct_index,explanation,source_url FROM questions WHERE id=?');$detail->execute([$qid]);
   $question=$detail->fetch(PDO::FETCH_ASSOC);
   $clubName=$q->prepare('SELECT name FROM clubs WHERE id=?');$clubName->execute([$cid]);
   if(!$question||!notifyQuestionReport($question,(string)$clubName->fetchColumn(),$date,$reason,$reportId))error_log('ClubDailyFive report notification could not be queued: '.$reportId);
  }catch(Throwable $e){error_log('ClubDailyFive report notification failed: '.$reportId);}
 }
 respond(200,true);
}
if(!in_array($game,['daily','wordle'],true)||!in_array($event,['selected','started','completed','shared'],true)||($d['play_date']??'')!==date('Y-m-d'))respond(422,false);
$a->beginTransaction();
if($event==='started'&&($d['active_day']??false)===true){
 $a->prepare('INSERT INTO returning_activity(event_date,active,returned_count) VALUES(?,1,?) ON CONFLICT(event_date) DO UPDATE SET active=active+1,returned_count=returned_count+excluded.returned_count')->execute([date('Y-m-d'),($d['returning']??false)===true?1:0]);
}
$s=$a->prepare('INSERT INTO game_funnel(event_date,club_slug,game,event,total) VALUES(?,?,?,?,1) ON CONFLICT(event_date,club_slug,game,event) DO UPDATE SET total=total+1');$s->execute([date('Y-m-d'),$club,$game,$event]);
$a->commit();
$a->prepare('DELETE FROM game_funnel WHERE event_date<?')->execute([date('Y-m-d',strtotime('-90 days'))]);
respond(200,true);
