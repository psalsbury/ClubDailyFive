window.cdfEvent=async function(club,game,event){
 const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const key='cdf:funnel:'+date+':'+club+':'+game+':'+event;
 const send=async()=>{try{
  if(localStorage.getItem(key))return;
  const last=localStorage.getItem('cdf:last-play-day'),first=event==='started'&&localStorage.getItem('cdf:active-day')!==date;
  const gap=last?(Date.parse(date+'T12:00:00Z')-Date.parse(last+'T12:00:00Z'))/86400000:0;
  const r=await fetch('/engagement.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({club,game,event,play_date:date,active_day:first,returning:first&&gap>=1&&gap<=7}),keepalive:true});
  if(r.ok){localStorage.setItem(key,'1');if(event==='started'){localStorage.setItem('cdf:last-play-day',date);if(first)localStorage.setItem('cdf:active-day',date)}}
 }catch(e){}};
 if(navigator.locks)await navigator.locks.request('cdf:engagement',send);else await send();
};
