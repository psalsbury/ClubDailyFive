<?php
declare(strict_types=1);
date_default_timezone_set('Europe/London');

const DB_PATH = '/var/lib/predictioncomp/clubquiz.sqlite';

function db(): PDO {
    $pdo = new PDO('sqlite:' . DB_PATH, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=4000;');
    return $pdo;
}

function h(string $value): string { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }

$pdo = db();
$clubs = $pdo->query("SELECT slug,name,accent,logo_path FROM clubs WHERE active=1 ORDER BY name")->fetchAll(PDO::FETCH_ASSOC);
$slug = preg_replace('/[^a-z0-9-]/', '', strtolower((string)($_GET['club'] ?? '')));
$club = null;
if ($slug !== '') {
    $stmt = $pdo->prepare('SELECT id,slug,name,accent,logo_path FROM clubs WHERE slug=? AND active=1');
    $stmt->execute([$slug]);
    $club = $stmt->fetch(PDO::FETCH_ASSOC) ?: null;
}

$questions = [];
$quizDate = (new DateTimeImmutable('now', new DateTimeZone('Europe/London')))->format('Y-m-d');
$sourceQuizDate = $quizDate;
if ($club) {
    // Always serve the newest complete round. A failed or partial midnight
    // publication must never leave a club with an empty quiz.
    $dateStmt = $pdo->prepare('SELECT quiz_date
        FROM daily_questions
        WHERE club_id=? AND quiz_date<=?
        GROUP BY quiz_date
        HAVING COUNT(*)=5
        ORDER BY quiz_date DESC LIMIT 1');
    $dateStmt->execute([(int)$club['id'], $quizDate]);
    $sourceQuizDate = (string)($dateStmt->fetchColumn() ?: $quizDate);

    $stmt = $pdo->prepare('SELECT q.id,q.question_text,q.options_json,q.correct_index,q.explanation,q.source_url,q.source_label,dq.position
        FROM daily_questions dq JOIN questions q ON q.id=dq.question_id
        WHERE dq.club_id=? AND dq.quiz_date=? ORDER BY dq.position');
    $stmt->execute([(int)$club['id'], $sourceQuizDate]);
    $questions = $stmt->fetchAll(PDO::FETCH_ASSOC);
}
$dateLabel = (new DateTimeImmutable($quizDate))->format('j F Y');
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07101e">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<title><?= $club ? h($club['name']).' — ClubDailyFive.com' : 'ClubDailyFive.com — The Daily Football Quiz' ?></title>
<meta name="description" content="ClubDailyFive.com — five fresh questions about your football club every day. Play, learn and share your score.">
<style>
:root{--ink:#f7f8fc;--muted:#a9b2c4;--panel:#111c31;--line:#273650;--accent:<?= h($club['accent'] ?? '#ffcc33') ?>;--good:#2ecc8f;--bad:#ff6475;--bg:#07101e}*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 80% -10%,color-mix(in srgb,var(--accent) 24%,transparent),transparent 36rem),var(--bg);min-height:100vh}.wrap{width:min(760px,calc(100% - 28px));margin:auto}.top{display:flex;align-items:center;justify-content:space-between;padding:22px 0}.brand{display:inline-flex;align-items:center;text-decoration:none;min-width:0}.brand img{display:block;width:clamp(230px,42vw,360px);height:auto}.brand:focus-visible{outline:2px solid var(--accent);outline-offset:5px;border-radius:4px}.date{color:var(--muted);font-size:.82rem}.hero{padding:64px 0 28px}.eyebrow{color:var(--accent);text-transform:uppercase;letter-spacing:.14em;font-weight:800;font-size:.75rem}.hero h1{font-size:clamp(2.7rem,11vw,5.5rem);line-height:.92;letter-spacing:-.07em;margin:.25em 0}.hero p{color:var(--muted);font-size:1.1rem;line-height:1.6;max-width:600px}.club-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:18px 0 64px}.club{min-height:72px;padding:16px;border:1px solid var(--line);border-radius:16px;background:rgba(17,28,49,.72);color:var(--ink);text-decoration:none;font-weight:750;display:flex;align-items:center;justify-content:space-between;transition:.18s}.club:hover,.club:focus-visible{border-color:var(--accent);transform:translateY(-2px);outline:none}.club span{color:var(--muted)}.quiz-head{padding:30px 0 18px}.quiz-head h1{font-size:clamp(2rem,8vw,3.8rem);letter-spacing:-.055em;margin:.2em 0}.progress{display:flex;gap:7px;margin:22px 0}.pip{height:5px;flex:1;background:var(--line);border-radius:99px}.pip.done{background:var(--accent)}.card{border:1px solid var(--line);border-radius:22px;background:rgba(17,28,49,.9);padding:clamp(20px,5vw,34px);min-height:430px;display:flex;flex-direction:column}.count{color:var(--accent);font-weight:800;font-size:.78rem;letter-spacing:.1em;text-transform:uppercase}.question{font-size:clamp(1.45rem,5vw,2rem);line-height:1.18;letter-spacing:-.035em;margin:14px 0 22px;min-height:76px}.answers{display:grid;gap:10px}.answer{width:100%;text-align:left;border:1px solid var(--line);background:#0b1628;color:var(--ink);padding:15px 16px;border-radius:13px;font:inherit;font-weight:680;cursor:pointer;min-height:54px}.answer:hover:not(:disabled){border-color:var(--accent)}.answer.correct{border-color:var(--good);background:color-mix(in srgb,var(--good) 13%,#0b1628)}.answer.wrong{border-color:var(--bad);background:color-mix(in srgb,var(--bad) 13%,#0b1628)}.answer:disabled{cursor:default}.feedback{margin-top:18px;border-top:1px solid var(--line);padding-top:16px;min-height:98px;visibility:hidden;color:var(--muted);line-height:1.5}.feedback.show{visibility:visible}.feedback strong{color:var(--ink)}.feedback a{color:var(--accent)}.next{margin-top:auto;align-self:flex-end;background:var(--accent);color:#06101d;border:0;border-radius:12px;padding:12px 20px;font-weight:900;cursor:pointer;visibility:hidden}.next.show{visibility:visible}.result{text-align:center;padding:26px 0}.score{font-size:5rem;font-weight:950;letter-spacing:-.08em;color:var(--accent)}.tiles{font-size:1.65rem;letter-spacing:.1em;margin:10px 0 24px}.share-actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;width:min(520px,100%);margin:20px auto 0}.share-action{min-height:48px;padding:10px 8px;border:1px solid var(--line);border-radius:12px;background:#0b1628;color:var(--ink);font:inherit;font-size:.86rem;font-weight:850;cursor:pointer;text-decoration:none;display:flex;align-items:center;justify-content:center}.share-action:hover,.share-action:focus-visible{border-color:var(--accent);outline:none;transform:translateY(-1px)}.share-action.primary{background:var(--accent);border-color:var(--accent);color:#06101d}@media(max-width:430px){.share-actions{grid-template-columns:repeat(2,1fr)}}.again{display:block;color:var(--muted);margin-top:18px}.foot{color:#778399;font-size:.76rem;padding:36px 0;text-align:center}.empty{padding:40px;border:1px solid var(--line);border-radius:20px;background:var(--panel)}@media(min-width:620px){.club-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:430px){.wrap{width:min(100% - 20px,760px)}.top{padding:16px 0}.brand img{width:230px}.date{font-size:.68rem}.hero{padding-top:38px}.card{min-height:480px;padding:20px}.question{min-height:100px}.feedback{min-height:116px}.answer{min-height:58px}}
/* Hidden must override component display modes when views change. */
[hidden]{display:none!important}
.streak-mini{color:var(--muted);font-size:.78rem;margin-top:5px}.streak-mini b{color:var(--ink)}.streaks{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:390px;margin:18px auto 22px}.streak-box{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:13px}.streak-number{display:block;color:var(--accent);font-size:1.75rem;font-weight:950}.streak-label{color:var(--muted);font-size:.72rem}
/* Responsive crest grid and single-screen mobile quiz */
.club img{width:42px;height:42px;object-fit:contain;flex:0 0 auto}.club-name{line-height:1.1;text-align:right;margin-left:auto}
@media(max-width:600px){body.quiz-page{overflow:hidden}.wrap{width:min(100% - 20px,760px)}.top{height:52px;padding:9px 0}.hero{padding:14px 0 6px}.hero h1{font-size:2.25rem;margin:.15em 0}.hero p{font-size:.82rem;line-height:1.3;margin:.35em 0}.club-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:6px 0 10px}.club{height:88px;min-height:88px;padding:6px 2px 5px;gap:3px;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:48px 26px;justify-content:stretch;justify-items:center;align-items:center;border-radius:10px;font-size:.59rem;box-shadow:none}.club::before{content:none}.club img{grid-area:1/1;display:block;width:42px;height:42px;align-self:center;justify-self:center;object-fit:contain}.club .club-name{grid-area:2/1;color:var(--ink);width:100%;height:26px;margin:0;display:flex;align-items:flex-start;justify-content:center;text-align:center;line-height:1.1;overflow-wrap:normal;word-break:normal;padding-top:1px}.quiz-head{height:98px;padding:7px 0 3px}.quiz-head h1{font-size:1.65rem;margin:.08em 0}.progress{margin:8px 0}.card{height:calc(100dvh - 150px);min-height:0;padding:12px 15px;border-radius:16px}.question{font-size:1.12rem;min-height:50px;margin:7px 0}.answers{gap:6px}.answer{min-height:42px;padding:8px 11px;font-size:.86rem}.feedback{min-height:72px;margin-top:7px;padding-top:7px;font-size:.76rem;line-height:1.25}.next{padding:8px 14px}.foot{display:none}.result{padding:8px 0}.score{font-size:4rem}}
</style>
</head>
<body class="<?= $club ? 'quiz-page' : 'home-page' ?>">
<main class="wrap">
<header class="top"><a class="brand" href="/" aria-label="ClubDailyFive.com home"><img src="/assets/clubdailyfive-logo.svg" alt="ClubDailyFive.com" width="360" height="60"></a><span class="date"><?= h($dateLabel) ?></span></header>
<?php if (!$club): ?>
<div id="homeChooser"><section class="hero"><div class="eyebrow">Premier League edition</div><h1>Five questions.<br>One club.</h1><p>Pick your team for four questions from the 300-question club bank and one fresh question from current form. If your club has not played in the last 7 days, the fresh question switches to the current season. A complete round lands at midnight UK time.</p></section>
<section class="club-grid" aria-label="Choose your club"><?php foreach($clubs as $c): ?><a class="club" href="/?club=<?= h($c['slug']) ?>"><img src="<?= h($c['logo_path']) ?>" alt="" width="42" height="42"><span class="club-name"><?= h($c['name']) ?></span></a><?php endforeach ?></section></div>
<section class="result" id="homeResult" hidden><div class="eyebrow">Today’s result</div><div class="score" id="homeScore"></div><h2 id="homeClub"></h2><div class="tiles" id="homeTiles"></div><div class="streaks"><div class="streak-box"><span class="streak-number" id="homeCompletion">0</span><span class="streak-label">🔥 completion streak</span></div><div class="streak-box"><span class="streak-number" id="homePerfect">0</span><span class="streak-label">⭐ perfect 5/5 streak</span></div></div><p>Today’s round is complete. Come back tomorrow for five new questions.</p><div class="share-actions" aria-label="Share your result"><button class="share-action primary" id="homeWhatsApp">WhatsApp</button><button class="share-action" id="homeFacebook">Facebook</button><button class="share-action" id="homeX">X</button><button class="share-action" id="homeCopy">Copy result</button></div></section>
<script>
(()=>{
const date=<?= json_encode($quizDate) ?>,key=`dailyfive:daily:${date}`;let r;
try{r=JSON.parse(localStorage.getItem(key))}catch(e){}
if(!r){for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i)||'';if(k.startsWith('dailyfive:')&&k.endsWith(`:${date}`)&&!k.includes(':streaks:')&&!k.includes(':daily:')){try{r=JSON.parse(localStorage.getItem(k));r.club=k.slice(10,-date.length-1);const s=JSON.parse(localStorage.getItem(`dailyfive:streaks:${r.club}`)||'{}');r.completion=s.completion||0;r.perfect=s.perfect||0;localStorage.setItem(key,JSON.stringify(r));break}catch(e){}}}}
if(r&&!r.roundId)r=null;if(!r)return;
document.getElementById('homeChooser').hidden=true;document.getElementById('homeResult').hidden=false;
document.getElementById('homeScore').textContent=`${r.score}/5`;document.getElementById('homeClub').textContent=`${r.club||'Your club'} Daily Five`;
document.getElementById('homeTiles').textContent=(r.marks||[]).map(x=>x?'🟩':'⬛').join('');
document.getElementById('homeCompletion').textContent=r.completion||0;document.getElementById('homePerfect').textContent=r.perfect||0;
const url=`https://clubdailyfive.com/${r.clubSlug?`?club=${encodeURIComponent(r.clubSlug)}`:''}`;
const message=`ClubDailyFive.com — ${r.club||'My club'}
${date}  ${r.score}/5
${(r.marks||[]).map(x=>x?'🟩':'⬛').join('')}
🔥 ${r.completion||0} day streak  ⭐ ${r.perfect||0} perfect

Can you beat me?
${url}`;
document.getElementById('homeWhatsApp').onclick=()=>window.open(`https://wa.me/?text=${encodeURIComponent(message)}`,'_blank','noopener,noreferrer');
document.getElementById('homeFacebook').onclick=()=>window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,'_blank','noopener,noreferrer');
document.getElementById('homeX').onclick=()=>window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(message.replace(url,'').trim())}&url=${encodeURIComponent(url)}`,'_blank','noopener,noreferrer');
document.getElementById('homeCopy').onclick=async e=>{try{await navigator.clipboard.writeText(message);e.currentTarget.textContent='Copied!'}catch(err){}};
})();
</script>
<?php elseif (count($questions) !== 5): ?>
<section class="quiz-head"><div class="eyebrow"><?= h($club['name']) ?></div><h1>Today’s five</h1></section><div class="empty"><h2>The next round is being prepared.</h2><p>Come back shortly for five fresh questions.</p><a class="again" href="/">Choose another club</a></div>
<?php else: ?>
<section class="quiz-head" id="quizHead"><div class="eyebrow"><?= h($club['name']) ?> · 4 club bank + 1 fresh daily</div><h1>Today’s five</h1><div class="streak-mini" id="streakMini" hidden></div><div class="progress" id="progress" aria-label="Quiz progress"></div></section>
<section class="card" id="quiz" aria-live="polite"><div class="count" id="count"></div><h2 class="question" id="question"></h2><div class="answers" id="answers"></div><div class="feedback" id="feedback"></div><button class="next" id="next">Next question</button></section>
<section class="result" id="result" hidden><div class="eyebrow">Full time</div><div class="score" id="score"></div><h2 id="resultClub"><?= h($club['name']) ?> Daily Five</h2><div class="tiles" id="tiles"></div><div class="streaks"><div class="streak-box"><span class="streak-number" id="completionStreak">0</span><span class="streak-label">🔥 completion streak</span></div><div class="streak-box"><span class="streak-number" id="perfectStreak">0</span><span class="streak-label">⭐ perfect 5/5 streak</span></div></div><p>Today’s round is complete. Come back tomorrow for five new questions.</p><div class="share-actions" aria-label="Share your result"><button class="share-action primary" id="shareWhatsApp">WhatsApp</button><button class="share-action" id="shareFacebook">Facebook</button><button class="share-action" id="shareX">X</button><button class="share-action" id="shareCopy">Copy result</button></div></section>
<script>
const questions=<?= json_encode(array_map(fn($q)=>['id'=>(int)$q['id'],'q'=>$q['question_text'],'o'=>json_decode($q['options_json'],true),'a'=>(int)$q['correct_index'],'e'=>$q['explanation'],'u'=>$q['source_url'],'s'=>$q['source_label']],$questions), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE) ?>;
const club=<?= json_encode($club['name']) ?>, clubSlug=<?= json_encode($club['slug']) ?>, quizDate=<?= json_encode($quizDate) ?>, roundId=questions.map(x=>x.id).join('-');
function anonymousPlayerId(){let id=localStorage.getItem('dailyfive:player-id');if(!id){id=(crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2));localStorage.setItem('dailyfive:player-id',id)}return id}
function track(event){fetch('/track.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({player_id:anonymousPlayerId(),club:clubSlug,event}),keepalive:true}).catch(()=>{})}
track('selected');track('started');
let at=0,score=0,marks=[],resultData=null;const $=id=>document.getElementById(id);
const streakKey=`dailyfive:streaks:${club}`;
const dailyKey=`dailyfive:daily:${quizDate}`;
function yesterday(date){const d=new Date(`${date}T12:00:00Z`);d.setUTCDate(d.getUTCDate()-1);return d.toISOString().slice(0,10)}
function readStreaks(){try{return JSON.parse(localStorage.getItem(streakKey))||{completion:0,perfect:0}}catch(e){return{completion:0,perfect:0}}}
function showReturningStreak(){const s=readStreaks();if(s.completion||s.perfect){$('streakMini').innerHTML=`🔥 <b>${s.completion||0}</b> completed &nbsp; ⭐ <b>${s.perfect||0}</b> perfect`;$('streakMini').hidden=false}}
function updateStreaks(){let s=readStreaks();if(s.lastCompleted!==quizDate){const prev=yesterday(quizDate);s.completion=s.lastCompleted===prev?(s.completion||0)+1:1;s.lastCompleted=quizDate;if(score===5){s.perfect=s.lastPerfect===prev?(s.perfect||0)+1:1;s.lastPerfect=quizDate}else{s.perfect=0;s.lastPerfect=null}localStorage.setItem(streakKey,JSON.stringify(s))}return s}
function readDailyResult(){try{const saved=JSON.parse(localStorage.getItem(dailyKey));if(saved&&saved.roundId===roundId)return saved;for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i)||'';if(k.startsWith('dailyfive:')&&k.endsWith(`:${quizDate}`)&&!k.includes(':streaks:')&&!k.includes(':daily:')){const old=JSON.parse(localStorage.getItem(k));if(old.roundId!==roundId)continue;old.club=k.slice(10,-quizDate.length-1);const s=JSON.parse(localStorage.getItem(`dailyfive:streaks:${old.club}`)||'{}');old.completion=s.completion||0;old.perfect=s.perfect||0;localStorage.setItem(dailyKey,JSON.stringify(old));return old}}}catch(e){}return null}
function showResult(r){resultData=r;score=Number(r.score)||0;marks=Array.isArray(r.marks)?r.marks:[];$('quiz').hidden=true;$('quizHead').hidden=true;$('result').hidden=false;$('score').textContent=`${score}/5`;$('resultClub').textContent=`${r.club||club} Daily Five`;$('tiles').textContent=marks.map(x=>x?'🟩':'⬛').join('');$('completionStreak').textContent=r.completion||0;$('perfectStreak').textContent=r.perfect||0}
$('progress').innerHTML=questions.map((_,i)=>`<span class="pip" id="p${i}"></span>`).join('');
function render(){const x=questions[at];$('count').textContent=`Question ${at+1} of 5`;$('question').textContent=x.q;$('answers').innerHTML='';$('feedback').className='feedback';$('feedback').innerHTML='';$('next').className='next';x.o.forEach((label,i)=>{const b=document.createElement('button');b.className='answer';b.textContent=label;b.onclick=()=>choose(i);$('answers').appendChild(b)});}
function choose(i){const x=questions[at],buttons=[...document.querySelectorAll('.answer')];buttons.forEach((b,n)=>{b.disabled=true;if(n===x.a)b.classList.add('correct');if(n===i&&i!==x.a)b.classList.add('wrong')});const ok=i===x.a;if(ok)score++;marks.push(ok);$('feedback').innerHTML=`<strong>${ok?'Correct.':'Not quite.'}</strong> ${x.e} <a href="${x.u}" target="_blank" rel="noopener">${x.s} ↗</a>`;$('feedback').classList.add('show');$('next').textContent=at===4?'See result':'Next question';$('next').classList.add('show');document.getElementById(`p${at}`).classList.add('done');}
$('next').onclick=()=>{if(++at<questions.length)render();else finish()};
function finish(){track('completed');localStorage.setItem(`dailyfive:${club}:${quizDate}`,JSON.stringify({score,marks}));const s=updateStreaks();const r={club,clubSlug,roundId,score,marks,completion:s.completion||0,perfect:s.perfect||0};localStorage.setItem(dailyKey,JSON.stringify(r));showResult(r)}
function currentShare(){
 const r=resultData||{club,clubSlug,score,marks,completion:0,perfect:0};
 const url=`https://clubdailyfive.com/?club=${encodeURIComponent(r.clubSlug||clubSlug)}`;
 const message=`ClubDailyFive.com — ${r.club||club}
${quizDate}  ${r.score}/5
${r.marks.map(x=>x?'🟩':'⬛').join('')}
🔥 ${r.completion||0} day streak  ⭐ ${r.perfect||0} perfect

Can you beat me?
${url}`;
 return {url,message};
}
$('shareWhatsApp').onclick=()=>{const x=currentShare();window.open(`https://wa.me/?text=${encodeURIComponent(x.message)}`,'_blank','noopener,noreferrer')};
$('shareFacebook').onclick=()=>{const x=currentShare();window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(x.url)}`,'_blank','noopener,noreferrer')};
$('shareX').onclick=()=>{const x=currentShare();window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(x.message.replace(x.url,'').trim())}&url=${encodeURIComponent(x.url)}`,'_blank','noopener,noreferrer')};
$('shareCopy').onclick=async e=>{const x=currentShare();try{await navigator.clipboard.writeText(x.message);e.currentTarget.textContent='Copied!'}catch(err){}};
const completed=readDailyResult();if(completed)showResult(completed);else{showReturningStreak();render()}
</script>
<?php endif ?>
<footer class="foot">Independent supporter quiz. Not affiliated with or endorsed by the Premier League or any club.</footer>
</main>
</body></html>
