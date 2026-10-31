// ClubDailyFive fan tables and private leagues (client side).
(()=>{
const TOKEN_KEY='cdf:lg-token';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
function token(){try{return localStorage.getItem(TOKEN_KEY)||null}catch(e){return null}}
function setToken(t){try{t?localStorage.setItem(TOKEN_KEY,t):localStorage.removeItem(TOKEN_KEY)}catch(e){}}
async function api(action,data={}){
 const t=token();
 const r=await fetch('/leagues-api.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...data,...(t?{token:t}:{})})});
 let j={};try{j=await r.json()}catch(e){}
 if(!r.ok||!j.ok){const err=new Error(j.error||'Could not connect. Please try again.');err.status=r.status;throw err}
 return j;
}
let mePromise=null;
function me(force=false){
 if(!token())return Promise.resolve(null);
 if(!mePromise||force)mePromise=api('me').then(j=>j.me).catch(e=>{if(e.status===404)setToken(null);return null});
 return mePromise;
}
function clubs(){return window.CDF_CLUBS||[]}
function clubName(slug){const c=clubs().find(c=>c.slug===slug);return c?c.name:slug}
function clubOptions(selected){
 const groups={'premier-league':'Premier League','championship':'Championship'};
 return Object.entries(groups).map(([k,label])=>`<optgroup label="${label}">${clubs().filter(c=>c.league===k).map(c=>`<option value="${esc(c.slug)}"${c.slug===selected?' selected':''}>${esc(c.name)}</option>`).join('')}</optgroup>`).join('');
}
// A finished round stored by the Daily Five page, if it has the answers chosen.
function storedRound(slug){
 try{const r=JSON.parse(localStorage.getItem(`dailyfive:result:${slug}:${today()}`));return r&&Array.isArray(r.choices)&&r.choices.length===5?r:null}catch(e){return null}
}
async function countStoredRound(slug){
 const r=storedRound(slug);if(!r)return null;
 try{return await api('result',{club:slug,choices:r.choices,play_date:today(),count:false})}catch(e){return null}
}

/** Name + club form, or a short summary when already set up. */
async function setup(el,opts={}){
 const m=await me();
 if(m){
  el.innerHTML=`<div class="lg-card lg-me"><p>Playing as <b>${esc(m.name)}</b> · ${esc(m.home_club_name)} fan${m.streak>1?` · 🔥 ${m.streak} days`:''}</p><button type="button" class="lg-link" data-edit>Change</button></div>`;
  el.querySelector('[data-edit]').onclick=()=>editForm(el,m,opts);
  opts.onReady&&opts.onReady(m);
  return m;
 }
 const club=opts.club||'';
 el.innerHTML=`<form class="lg-card lg-form" data-register>
  <h2>${esc(opts.title||'Get your name on the tables')}</h2>
  <p>${esc(opts.blurb||'Pick a name and your club. Your scores then count on your club’s fan table and in any private leagues you join.')}</p>
  <label>Your name<input name="name" maxlength="20" required autocomplete="nickname" placeholder="e.g. Pete"></label>
  <label>Your club<select name="home_club" required>${club?'':'<option value="">Choose…</option>'}${clubOptions(club)}</select></label>
  <button class="lg-button primary">${esc(opts.button||'Save')}</button>
  <p class="lg-small">No email or password. Your name is saved in this browser. Names are public on the tables.</p>
  <p class="lg-msg" role="status"></p></form>`;
 const f=el.querySelector('form');
 f.onsubmit=async e=>{
  e.preventDefault();const msg=f.querySelector('.lg-msg'),btn=f.querySelector('button');btn.disabled=true;msg.textContent='Saving…';
  try{
   const j=await api('register',{name:f.name.value,home_club:f.home_club.value});
   setToken(j.token);mePromise=Promise.resolve(j.me);
   await countStoredRound(j.me.home_club);
   if(opts.joinCode)await api('join_league',{code:opts.joinCode});
   const fresh=await me(true);
   opts.onDone?opts.onDone(fresh):location.reload();
  }catch(err){msg.textContent=err.message;btn.disabled=false}
 };
 opts.onReady&&opts.onReady(null);
 return null;
}
function editForm(el,m,opts){
 el.innerHTML=`<form class="lg-card lg-form">
  <h2>Your details</h2>
  <label>Your name<input name="name" maxlength="20" required value="${esc(m.name)}"></label>
  <label>Your club<select name="home_club">${clubOptions(m.home_club)}</select></label>
  <p class="lg-small">Changing club starts your scores again from zero.</p>
  <div class="lg-actions"><button class="lg-button primary">Save</button><button type="button" class="lg-button" data-cancel>Cancel</button></div>
  <p class="lg-small"><button type="button" class="lg-link" data-delete>Delete my name and scores</button></p>
  <p class="lg-msg" role="status"></p></form>`;
 const f=el.querySelector('form'),msg=f.querySelector('.lg-msg');
 f.querySelector('[data-cancel]').onclick=()=>setup(el,opts);
 f.querySelector('[data-delete]').onclick=async()=>{
  if(!confirm('Delete your name, scores and league places? This cannot be undone.'))return;
  try{await api('delete_me');setToken(null);location.reload()}catch(err){msg.textContent=err.message}
 };
 f.onsubmit=async e=>{
  e.preventDefault();
  if(f.home_club.value!==m.home_club&&!confirm('Changing club resets your scores to zero. Continue?'))return;
  msg.textContent='Saving…';
  try{await api('update',{name:f.name.value,home_club:f.home_club.value});if(f.home_club.value!==m.home_club)await countStoredRound(f.home_club.value);location.reload()}catch(err){msg.textContent=err.message}
 };
}

function markMe(m){
 if(!m)return;
 document.querySelectorAll(`[data-player="${CSS.escape(m.id)}"]`).forEach(li=>li.classList.add('me'));
}
function tabs(){
 document.querySelectorAll('.lg-tabs').forEach(bar=>{
  const card=bar.parentElement;
  bar.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{
   bar.querySelectorAll('[data-tab]').forEach(x=>x.setAttribute('aria-selected',String(x===b)));
   card.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==b.dataset.tab);
  });
 });
}
async function shareInvite(code,name){
 const url=`https://clubdailyfive.com/league/${code}`;
 const text=`Join my ClubDailyFive league "${name}": five questions on your club every day. Who knows their club best?`;
 const status=document.querySelector('[data-invite-status]');
 if(navigator.share){try{await navigator.share({title:name,text,url});return}catch(e){if(e.name==='AbortError')return}}
 try{await navigator.clipboard.writeText(`${text}\n${url}`);if(status)status.textContent='Invite link copied. Paste it into your group chat.'}
 catch(e){if(status)status.textContent=url}
}

/** /leagues hub. */
async function hubPage(){
 const el=document.querySelector('[data-setup]');
 const m=await setup(el,{onDone:()=>location.reload()});
 if(!m)return;
 const list=document.querySelector('[data-league-list]');
 document.querySelector('[data-create]').hidden=false;document.querySelector('[data-join]').hidden=false;
 if(m.leagues.length){
  document.querySelector('[data-my-leagues]').hidden=false;
  list.innerHTML=m.leagues.map(l=>`<li><a href="/league/${esc(l.code)}">${esc(l.name)}</a><small>${l.members} ${l.members===1?'member':'members'}</small></li>`).join('');
 }
 const cf=document.querySelector('[data-create-form]');
 cf.onsubmit=async e=>{e.preventDefault();const msg=cf.querySelector('.lg-msg');msg.textContent='Creating…';
  try{const j=await api('create_league',{name:cf.name.value});location.href='/league/'+j.code+'?new=1'}catch(err){msg.textContent=err.message}};
 const jf=document.querySelector('[data-join-form]');
 jf.onsubmit=async e=>{e.preventDefault();const msg=jf.querySelector('.lg-msg');msg.textContent='Joining…';
  try{const j=await api('join_league',{code:jf.code.value});location.href='/league/'+j.code}catch(err){msg.textContent=err.message}};
}

/** /league/<CODE> page. */
async function leaguePage(box){
 const code=box.dataset.leagueCode,name=box.dataset.leagueName;
 const m=await me();
 box.querySelectorAll('[data-invite]').forEach(b=>b.onclick=()=>shareInvite(code,name));
 if(!m){
  box.querySelector('[data-join-box]').hidden=false;
  setup(box.querySelector('[data-setup]'),{joinCode:code,title:'Join '+name,button:'Join league',blurb:'Choose a name your mates will recognise, and the club you support.'});
  return;
 }
 markMe(m);
 const member=m.leagues.some(l=>l.code===code);
 if(!member){
  box.querySelector('[data-joinable]').hidden=false;
  box.querySelector('[data-join-now]').onclick=async()=>{try{await api('join_league',{code});location.reload()}catch(err){box.querySelector('[data-invite-status]').textContent=err.message}};
  return;
 }
 box.querySelector('[data-member-box]').hidden=false;
 box.querySelector('[data-play-link]').href='/daily-five/'+m.home_club;
 if(m.today!==null){box.querySelector('[data-play-link]').hidden=true}
 box.querySelector('[data-member-line]').innerHTML=m.today!==null
  ?`You scored <b>${m.today}/5</b> today for ${esc(m.home_club_name)}. Invite more mates to make it a proper league.`
  :`You haven’t played today. Your ${esc(m.home_club_name)} Daily Five counts for this league.`;
 if(new URLSearchParams(location.search).has('new'))box.querySelector('[data-invite-status]').textContent='League created. Now invite your mates: tap “Invite friends” and send the link to your group chat.';
 const leave=document.querySelector('[data-leave-box]');leave.hidden=false;
 leave.querySelector('[data-leave]').onclick=async()=>{if(!confirm('Leave '+name+'?'))return;try{await api('leave_league',{code});location.href='/leagues'}catch(err){alert(err.message)}};
}

/** Club table page: league filter, with positions renumbered within the filter. */
function clubTablePage(){
 const buttons=document.querySelectorAll('[data-league-filter]');
 const apply=league=>{
  buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.leagueFilter===league)));
  document.querySelectorAll('.lg-clubs').forEach(list=>{
   let i=0,shown=0,prevAvg=null,pos=0;const rows=[...list.children];
   rows.forEach(li=>{li.hidden=!!league&&li.dataset.league!==league});
   const visible=rows.filter(li=>!li.hidden);
   const avgs=visible.map(li=>li.querySelector('.lg-pts').textContent);
   visible.forEach((li,n)=>{i++;if(avgs[n]!==prevAvg){pos=i;prevAvg=avgs[n]}const joint=avgs.filter(a=>a===avgs[n]).length>1;li.querySelector('.lg-pos').textContent=(joint?'=':'')+pos;shown++});
  });
  document.querySelectorAll('.lg-waiting').forEach(p=>{const items=[...p.querySelectorAll('span[data-league]')];items.forEach(x=>x.hidden=!!league&&x.dataset.league!==league);p.hidden=!items.some(x=>!x.hidden)});
 };
 buttons.forEach(b=>b.onclick=()=>apply(b.dataset.leagueFilter));
}

/** Fan table page. */
async function fanPage(el){
 const m=await setup(el,{club:el.dataset.club});
 markMe(m);
}

/** Daily Five result screen panel. opts: {club, clubSlug, choices, score, panel} */
async function result(opts){
 const panel=opts.panel;if(!panel)return null;
 const countKey=`cdf:lg-counted:${opts.clubSlug}:${today()}`;
 let stats=null;
 try{
  if(Array.isArray(opts.choices)&&opts.choices.length===5){
   let first=false;try{first=!localStorage.getItem(countKey)}catch(e){}
   stats=await api('result',{club:opts.clubSlug,choices:opts.choices,play_date:today(),count:first});
   try{localStorage.setItem(countKey,'1')}catch(e){}
  }else{
   const r=await fetch('/leagues-api.php?club='+encodeURIComponent(opts.clubSlug));stats=await r.json();
  }
 }catch(e){return null}
 if(!stats||!stats.ok||!Array.isArray(stats.dist))return null;
 const m=stats.me||null;if(m)mePromise=Promise.resolve(m);
 const fan=opts.club;
 const max=Math.max(1,...stats.dist);
 let html=`<h3>Today’s ${esc(fan)} players</h3>`;
 if(stats.played>1){
  html+=`<p class="lg-lede"><b>${stats.played}</b> played · average <b>${stats.average.toFixed(1)}</b>${stats.beat>0?` · you beat <b>${stats.beat}%</b>`:''}</p>`;
  html+=`<div class="lg-dist small" aria-hidden="true">${stats.dist.map((n,s)=>`<div class="lg-bar${s===opts.score?' mine':''}"><span style="height:${Math.round(100*n/max)}%"></span><b>${s}</b></div>`).join('')}</div>`;
 }else{
  html+=`<p class="lg-lede">You’re one of the first to play today. Check back later to see how you compare.</p>`;
 }
 if(m&&m.home_club===opts.clubSlug&&stats.my_rank){
  html+=`<p class="lg-rank">You’re <b>${esc(stats.my_rank.label)}</b> of ${stats.my_rank.of} on the ${esc(fan)} fan table</p>`;
 }else if(m&&m.home_club!==opts.clubSlug){
  html+=`<p class="lg-small">Your tables count ${esc(m.home_club_name)} rounds only, so this one is just for fun.</p>`;
 }
 const ct=stats.club_table,rv=stats.rival;
 if(rv)html+=`<p class="lg-vs">Today: ${esc(fan)} fans <b>${rv.my_average.toFixed(1)}</b> v <b>${rv.average.toFixed(1)}</b> ${esc(rv.name)} fans</p>`;
 if(ct&&ct.of>1)html+=`<p class="lg-small" style="text-align:center">${esc(fan)} are <b>${esc(ct.label)}</b> of ${ct.of} clubs on today’s <a href="/club-table">club table</a></p>`;
 else html+=`<p class="lg-small" style="text-align:center">See which fans know their club best on the <a href="/club-table">club table</a></p>`;
 html+=`<div class="lg-actions"><a class="lg-button" href="/fans/${esc(opts.clubSlug)}">${esc(fan)} fan table</a>`;
 html+=m&&m.leagues.length?`<a class="lg-button" href="/league/${esc(m.leagues[0].code)}">${esc(m.leagues[0].name)}</a>`:`<a class="lg-button" href="/leagues">Start a league with mates</a>`;
 html+=`</div>`;
 if(!m)html+=`<div data-result-setup></div>`;
 panel.innerHTML=html;panel.hidden=false;
 if(!m)setup(panel.querySelector('[data-result-setup]'),{club:opts.clubSlug,title:`Put your name on the ${fan} fan table`,blurb:'Pick a name and your club. Your score today goes straight on the table.',button:'Add me to the table',onDone:()=>result({...opts})});
 const extra={played:stats.played,beat:stats.beat,rank:stats.my_rank||null,clubTable:stats.club_table||null};
 opts.onStats&&opts.onStats(extra);
 return extra;
}

window.CDFLeagues={token,api,me,setup,result};
document.addEventListener('DOMContentLoaded',()=>{
 tabs();
 const league=document.querySelector('[data-league-code]');
 if(league){leaguePage(league);return}
 if(document.querySelector('[data-create-form]')){hubPage();return}
 if(document.querySelector('[data-league-filter]')){clubTablePage();return}
 const fans=document.querySelector('[data-setup][data-club]');
 if(fans&&!document.getElementById('result'))fanPage(fans);
});
})();
