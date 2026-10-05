(()=>{
 const dialog=document.getElementById('wordleGuide'),offer=document.getElementById('walkthroughOffer');
 if(!dialog||!offer)return;
 const key='cdf:wordle-guide:v1';let step=0,returnFocus=null;
 const steps=[
 ['Find today’s player','<p>You have <strong>five guesses</strong> to identify a player who has made a competitive senior appearance for your chosen club.</p><p>Type at least two letters, then select a name from the suggestions. Each selection uses one guess.</p>'],
 ['Read the five clues','<ul><li><strong>Debut age:</strong> age at their first competitive appearance for this club.</li><li><strong>Position:</strong> prominent playing role.</li><li><strong>Nationality:</strong> recorded football nationality.</li><li><strong>Debut year:</strong> year of that first appearance.</li><li><strong>Previous clubs:</strong> distinct senior clubs before joining, including senior loan clubs.</li></ul>'],
 ['Green means an exact match','<p>A green clue matches the mystery player’s value. It does not necessarily mean you have guessed the right player.</p><div class="guide-example green">Debut year: 2018 = 2018</div><p>Use the green clues to narrow down your next choice.</p>'],
 ['Amber means close','<ul><li><strong>Debut age:</strong> within 2 years. Age 22 is close to 24.</li><li><strong>Position:</strong> one neighbouring category in Goalkeeper → Defender → Midfielder → Forward. Defender is close to Midfielder.</li><li><strong>Nationality:</strong> a different country on the same continent. France is close to Spain.</li><li><strong>Debut year:</strong> within 2 years. 2017 is close to 2019.</li><li><strong>Previous clubs:</strong> within 1. Three is close to four.</li></ul><div class="guide-example amber">Example: age 22, mystery age 24</div>'],
 ['Grey means keep looking','<div class="guide-example miss">Example: age 18, mystery age 25</div><p>A grey clue is outside the amber range. Combine all five clues when choosing your next player.</p><p>After five guesses, or a correct guess, the answer is revealed and you can share your result. A new player arrives at midnight UK time.</p>']
 ];
 function remember(){try{localStorage.setItem(key,'seen')}catch(e){}}
 function render(){document.getElementById('guideStep').textContent=`STEP ${step+1} OF ${steps.length}`;document.getElementById('guideTitle').textContent=steps[step][0];document.getElementById('guideBody').innerHTML=steps[step][1];document.getElementById('guideBack').hidden=step===0;document.getElementById('guideNext').textContent=step===steps.length-1?'Start playing':'Next';document.getElementById('guideTitle').focus();}
 function close(){remember();offer.hidden=true;dialog.close();(returnFocus?.closest('#walkthroughOffer')?document.getElementById('guess'):returnFocus)?.focus();}
 document.querySelectorAll('[data-guide-open]').forEach(b=>b.addEventListener('click',()=>{returnFocus=b;step=0;dialog.showModal();render();}));
 document.getElementById('guideNext').onclick=()=>{if(step===steps.length-1)close();else{step++;render();}};
 document.getElementById('guideBack').onclick=()=>{if(step>0){step--;render();}};
 document.getElementById('guideClose').onclick=close;
 dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
 document.getElementById('guideDismiss').onclick=()=>{remember();offer.hidden=true;document.getElementById('guess')?.focus();};
 let seen=false,hasPlayed=false;try{seen=!!localStorage.getItem(key);for(let i=0;i<localStorage.length;i++){if(/^pwgame:|^pw:/.test(localStorage.key(i))){hasPlayed=true;break;}}}catch(e){}
 offer.hidden=seen||hasPlayed;
})();
