window.cdfEvent=async function(club,game,event){
 const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const key='cdf:funnel:'+date+':'+club+':'+game+':'+event;
 const send=async()=>{try{if(localStorage.getItem(key))return;const r=await fetch('/engagement.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({club,game,event,play_date:date}),keepalive:true});if(r.ok)localStorage.setItem(key,'1')}catch(e){}};
 if(navigator.locks)await navigator.locks.request(key,send);else await send();
};
