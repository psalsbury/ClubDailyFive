let attempts=0,done=false,marks=[],box=document.querySelector('#guess'),sug=document.querySelector('#suggestions'),rows=document.querySelector('#rows');
const stateKey='pwgame:'+GAME.date+':'+GAME.club;
const keys=['debut_age','position','nationality','debut_year','prior_clubs'];

function saveState(){
  localStorage.setItem(stateKey,JSON.stringify({
    attempts,done,marks,rows:rows.innerHTML,
    result:document.querySelector('#result').innerHTML
  }));
}

function appendAnswer(answer){
  if(!answer||!answer.values||rows.querySelector('.answerrow'))return;
  let row=document.createElement('div');
  row.className='guessrow answerrow';
  row.innerHTML='<div class="answer-banner"><span>✓ CORRECT PLAYER</span><strong>'+answer.answer+'</strong></div>'+keys.map(k=>'<span class="green">'+answer.values[k]+'</span>').join('');
  rows.append(row);
}

async function getAnswer(){
  return await (await fetch('api.php?action=answer&club='+GAME.club+'&_='+Date.now(),{cache:'no-store'})).json();
}

function setCompletedView(){
  document.body.classList.add('game-complete');
}

function restoreState(){
  let s;
  try{s=JSON.parse(localStorage.getItem(stateKey)||'null')}catch(e){}
  if(!s)return;
  attempts=Number(s.attempts)||0;
  done=!!s.done;
  marks=Array.isArray(s.marks)?s.marks:[];
  rows.innerHTML=s.rows||'';
  document.querySelector('#result').innerHTML=s.result||'';
  document.querySelector('#left').textContent=Math.max(0,5-attempts);
  if(done){
    box.disabled=true;
    setCompletedView();
    document.querySelector('#share').hidden=false;
    document.querySelector('#choose-club').hidden=false;
    let summary={};
    try{summary=JSON.parse(localStorage.getItem('pw:'+GAME.club)||'{}')}catch(e){}
    if(summary.won===true&&!rows.querySelector('.answerrow')){
      let last=rows.querySelector('.guessrow:last-child');
      if(last){
        last.classList.add('answerrow','won-answer');
        let name=last.querySelector('b');
        if(name){
          let banner=document.createElement('div');
          banner.className='answer-banner';
          banner.innerHTML='<span>✓ CORRECT PLAYER</span><strong>'+name.textContent+'</strong>';
          name.remove();
          last.prepend(banner);
        }
        saveState();
      }
    }else if(summary.won===false&&!rows.querySelector('.answerrow')){
      getAnswer().then(answer=>{
        appendAnswer(answer);
        document.querySelector('#result').innerHTML='<h2>Out of guesses</h2><p>The correct player and their data are shown above.</p>';
        saveState();
      });
    }
  }
}

restoreState();
fetch('api.php?action=start&club='+GAME.club,{cache:'no-store'});

let timer;
box.oninput=()=>{
  clearTimeout(timer);
  timer=setTimeout(async()=>{
    let q=box.value.trim();
    if(q.length<2){sug.innerHTML='';return}
    let a=await(await fetch('api.php?action=suggest&club='+GAME.club+'&q='+encodeURIComponent(q),{cache:'no-store'})).json();
    sug.innerHTML=a.map(x=>'<button data-id="'+x.id+'">'+x.name+'</button>').join('');
    sug.querySelectorAll('button').forEach(b=>b.onclick=()=>play(b.dataset.id,b.textContent));
  },120)
};

async function play(id,name){
  if(done)return;
  sug.innerHTML='';
  box.value='';
  let r=await(await fetch('api.php?action=guess&club='+GAME.club+'&player='+id,{cache:'no-store'})).json();
  attempts++;
  let row=document.createElement('div');
  row.className='guessrow'+(r.correct?' answerrow':'');
  row.innerHTML=r.correct
    ? '<div class="answer-banner"><span>✓ CORRECT PLAYER</span><strong>'+r.name+'</strong></div>'+keys.map(k=>'<span class="green">'+r.values[k]+'</span>').join('')
    : '<b>'+r.name+'</b>'+keys.map(k=>'<span class="'+r.marks[k]+'">'+r.values[k]+'</span>').join('');
  rows.append(row);
  marks.push(keys.map(k=>r.marks[k]==='green'?'🟩':r.marks[k]==='amber'?'🟨':'⬛').join(''));
  document.querySelector('#left').textContent=5-attempts;
  saveState();
  if(r.correct||attempts===5)finish(r.correct);
}

async function finish(won){
  done=true;
  box.disabled=true;
  setCompletedView();
  let r=await(await fetch('api.php?action=finish&club='+GAME.club+'&won='+(won?1:0)+'&guesses='+attempts+'&_='+Date.now(),{cache:'no-store'})).json();
  if(!won){
    if(!r.values)r=await getAnswer();
    appendAnswer(r);
  }
  let key='pw:'+GAME.club,old=JSON.parse(localStorage.getItem(key)||'{}'),
      y=new Date(Date.now()-86400000).toLocaleDateString('en-CA',{timeZone:'Europe/London'}),
      streak=(old.date===y?old.streak:0)+1;
  localStorage.setItem(key,JSON.stringify({date:GAME.date,done:true,streak:streak,won:won}));
  document.querySelector('#result').innerHTML=won
    ?'<h2>🎉 You got it in '+attempts+'!</h2>'
    :'<h2>Out of guesses</h2><p>The correct player and their data are shown above.</p>';
  saveState();
  let sh=document.querySelector('#share');
  sh.hidden=false;
  document.querySelector('#choose-club').hidden=false;
  sh.onclick=async()=>{
    let t='Player Wordle — '+GAME.name+' — '+GAME.date+'\n'+(won?attempts:'X')+'/5\n'+marks.join('\n')+'\n🔥 Streak '+streak;
    if(navigator.share)navigator.share({text:t});
    else{await navigator.clipboard.writeText(t);sh.textContent='Copied!'}
  }
}
