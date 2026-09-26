(() => {
  if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (standalone) return;
  let visits = Number(localStorage.getItem('cdf:pwa-visits') || 0);
  if (!sessionStorage.getItem('cdf:pwa-visit-counted')) { visits++; localStorage.setItem('cdf:pwa-visits', String(visits)); sessionStorage.setItem('cdf:pwa-visit-counted', '1'); }
  const hasPlayed = Object.keys(localStorage).some(key => key.startsWith('dailyfive:result:') || key.startsWith('pw:'));
  if (visits < 2 && !hasPlayed) return;
  const button = document.createElement('button'); button.type = 'button'; button.textContent = '＋ Install app'; button.setAttribute('aria-label', 'Install ClubDailyFive app');
  Object.assign(button.style,{position:'fixed',right:'12px',bottom:'12px',zIndex:'2000',border:'1px solid #38d879',borderRadius:'999px',padding:'10px 14px',background:'#0b2018',color:'#f7f8fc',font:'700 13px system-ui',boxShadow:'0 8px 26px rgba(0,0,0,.35)',cursor:'pointer',display:'none'}); document.body.appendChild(button);
  let promptEvent = null;
  addEventListener('beforeinstallprompt', event => { event.preventDefault(); promptEvent = event; button.style.display = 'block'; });
  addEventListener('appinstalled', () => { button.remove(); promptEvent = null; });
  const isiOS = /iphone|ipad|ipod/i.test(navigator.userAgent); if (isiOS) button.style.display = 'block';
  button.addEventListener('click', async () => { if (promptEvent) { promptEvent.prompt(); await promptEvent.userChoice; promptEvent=null; button.remove(); } else if (isiOS) alert('To install ClubDailyFive, tap Share in Safari, then choose “Add to Home Screen”.'); });
})();
