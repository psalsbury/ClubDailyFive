<?php
declare(strict_types=1);
/** Queue an owner notification using the host's existing mail transport. */
function notifyQuestionReport(array $question,string $club,string $date,string $reason,int $reportId,bool $test=false): bool {
 $labels=['incorrect'=>'Incorrect answer','outdated'=>'Outdated statistic','repeated'=>'Repeated question'];
 $options=json_decode($question['options_json'],true);
 $answer=(string)($options[(int)$question['correct_index']]??'');
 $subject=($test?'[TEST] ':'').'ClubDailyFive question report #'.$reportId;
 $body=($test?"This is a test of your new question-report email notification. No player report was created.\n\n":"A player has reported a Daily Five question.\n\n")
 ."Club: ".$club."\nQuiz date: ".$date."\nIssue: ".($labels[$reason]??$reason)."\nReport ID: ".$reportId
 ."\n\nQuestion: ".$question['question_text']."\nCurrent answer: ".$answer."\nExplanation: ".$question['explanation']
 ."\n\nSource: ".$question['source_url']."\nReview reports: https://clubdailyfive.com/owner-stats/"
 ."\n\nThe question remains available until reviewed. Identical reports are grouped and do not send repeated emails.\n";
 return mail('pete@salsbury.co.uk',$subject,$body,[
 'From'=>'ClubDailyFive <admin@clubdailyfive.com>',
 'Reply-To'=>'admin@clubdailyfive.com',
 'MIME-Version'=>'1.0',
 'Content-Type'=>'text/plain; charset=UTF-8'
 ],'-fadmin@clubdailyfive.com');
}
