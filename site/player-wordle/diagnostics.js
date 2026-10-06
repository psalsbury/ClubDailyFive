// Counts only; never record typed names, identifiers or error messages.
(()=>{
 const sent=new Set(),originalFetch=window.fetch.bind(window);
 window.pwDiagnostic=event=>{
  if(sent.has(event))return;sent.add(event);
  originalFetch('/player-wordle/diagnostics.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({club:GAME.club,event}),keepalive:true}).catch(()=>{});
 };
 window.fetch=async(...args)=>{
  let action='';try{const u=new URL(typeof args[0]==='string'?args[0]:args[0].url,location.href);if(u.pathname==='/player-wordle/api.php')action=u.searchParams.get('action')||'';}catch(e){}
  try{const r=await originalFetch(...args);
   if(action&&!r.ok)pwDiagnostic('api_'+action+'_error');
   if(action&&r.ok&&['suggest','guess','finish','start','answer'].includes(action)){
    try{const data=await r.clone().json();
     if(action==='suggest')pwDiagnostic(Array.isArray(data)&&data.length?'suggestions_shown':'no_suggestions');
     if(action==='guess')pwDiagnostic(data.values&&data.marks?'guess_accepted':'api_guess_error');
    }catch(e){pwDiagnostic('api_'+action+'_error');}
   }return r;
  }catch(e){if(action)pwDiagnostic('api_'+action+'_error');throw e;}
 };
 addEventListener('error',()=>pwDiagnostic('javascript_error'));
 addEventListener('unhandledrejection',()=>pwDiagnostic('promise_error'));
 const box=document.getElementById('guess');
 box?.addEventListener('focus',()=>pwDiagnostic('input_focus'));
 box?.addEventListener('input',()=>{if(box.value.trim())pwDiagnostic('typing');});
 try{const s=JSON.parse(localStorage.getItem('pwgame:'+GAME.date+':'+GAME.club)||'null');if(s)pwDiagnostic(s.done?'restored_completed':'restored_in_progress');}catch(e){pwDiagnostic('storage_error');}
 pwDiagnostic('page_open');
 addEventListener('pagehide',()=>{if(typeof done!=='undefined'&&!done)pwDiagnostic('left_after_'+Math.max(0,Math.min(5,attempts))+'_guesses');});
})();
