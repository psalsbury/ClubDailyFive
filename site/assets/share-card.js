// Draws a 1080x1350 Daily Five result card in club colours. Returns a PNG Blob.
(()=>{
// Primary kit colours (the database accent is a site default for many clubs).
const KIT={'arsenal':'#ef0107','aston-villa':'#95bfe5','bournemouth':'#da291c','brentford':'#e30613','brighton':'#0057b8','chelsea':'#034694','coventry-city':'#69b3e7','crystal-palace':'#1b458f','everton':'#003399','fulham':'#ffffff','hull-city':'#f5a12d','ipswich-town':'#3a64a3','leeds-united':'#ffcd00','liverpool':'#c8102e','manchester-city':'#6cabdd','manchester-united':'#da291c','newcastle-united':'#ffffff','nottingham-forest':'#dd0000','sunderland':'#eb172b','tottenham-hotspur':'#ffffff','birmingham-city':'#0033a0','blackburn-rovers':'#009ee0','bolton-wanderers':'#ffffff','bristol-city':'#e21b23','burnley':'#8a1c4a','cardiff-city':'#0070b5','charlton-athletic':'#d4021d','derby-county':'#ffffff','lincoln-city':'#e30613','middlesbrough':'#e11b22','millwall':'#2b4d9b','norwich-city':'#fff200','portsmouth':'#1f4fb3','preston-north-end':'#ffffff','queens-park-rangers':'#1d5ba4','sheffield-united':'#ee2737','southampton':'#d71920','stoke-city':'#e03a3e','swansea-city':'#ffffff','watford':'#fbee23','west-bromwich-albion':'#1d3f8f','west-ham-united':'#7a263a','wolverhampton-wanderers':'#fdb913','wrexham':'#e2001a'};
const FONT='Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif';
function rgb(hex){const h=hex.replace('#','');return[0,2,4].map(i=>parseInt(h.slice(i,i+2),16))}
function lum([r,g,b]){const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(r)+.7152*f(g)+.0722*f(b)}
function mix(a,b,t){return a.map((v,i)=>Math.round(v+(b[i]-v)*t))}
function css(c,a=1){return `rgba(${c[0]},${c[1]},${c[2]},${a})`}
function round(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath()}
function fit(ctx,text,max,size,weight){let s=size;do{ctx.font=`${weight} ${s}px ${FONT}`;s-=2}while(ctx.measureText(text).width>max&&s>20);return s}
function load(src){return new Promise(res=>{if(!src)return res(null);const i=new Image();i.onload=()=>res(i);i.onerror=()=>res(null);i.src=src})}
function niceDate(d){try{return new Date(d+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}catch(e){return d}}

async function make(o){
 const W=1080,H=1350,c=document.createElement('canvas');c.width=W;c.height=H;const ctx=c.getContext('2d');
 const kit=rgb(KIT[o.clubSlug]||o.accent||'#ffcc33');
 // Text-safe accent: lift dark kit colours so they read on navy.
 const accent=lum(kit)<.12?mix(kit,[255,255,255],.45):kit;
 const bg=[7,16,30];
 ctx.fillStyle=css(bg);ctx.fillRect(0,0,W,H);
 let g=ctx.createRadialGradient(W*.85,-80,40,W*.85,-80,1100);g.addColorStop(0,css(kit,.55));g.addColorStop(.55,css(kit,.12));g.addColorStop(1,css(kit,0));ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
 g=ctx.createRadialGradient(80,H+60,20,80,H+60,700);g.addColorStop(0,css(kit,.28));g.addColorStop(1,css(kit,0));ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
 // Kit stripe down the left edge.
 ctx.fillStyle=css(kit);ctx.fillRect(0,0,18,H);
 ctx.textAlign='center';ctx.textBaseline='alphabetic';
 ctx.fillStyle=css([255,204,51]);ctx.font=`900 34px ${FONT}`;
 ctx.letterSpacing='6px';ctx.fillText('CLUBDAILYFIVE.COM',W/2,96);ctx.letterSpacing='0px';
 // Crest on a white disc so every badge (including monochrome ones) shows up.
 const crest=await load(o.crest);
 const cx=W/2,cy=290,R=150;
 ctx.save();ctx.shadowColor='rgba(0,0,0,.45)';ctx.shadowBlur=40;ctx.shadowOffsetY=12;ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.fill();ctx.restore();
 ctx.lineWidth=10;ctx.strokeStyle=css(kit);ctx.beginPath();ctx.arc(cx,cy,R+5,0,Math.PI*2);ctx.stroke();
 if(crest){const s=Math.min((R*1.45)/crest.width,(R*1.45)/crest.height);const w=crest.width*s,h=crest.height*s;ctx.drawImage(crest,cx-w/2,cy-h/2,w,h)}
 ctx.fillStyle='#f7f8fc';fit(ctx,o.club,W-140,74,900);ctx.fillText(o.club,W/2,535);
 ctx.fillStyle='#a9b2c4';ctx.font=`700 32px ${FONT}`;ctx.fillText(`Daily Five · ${niceDate(o.date)}`,W/2,588);
 // Score.
 ctx.fillStyle=css(accent);ctx.font=`950 250px ${FONT}`;ctx.fillText(`${o.score}/5`,W/2,830);
 // Tiles.
 const T=128,gap=24,tw=5*T+4*gap,tx=(W-tw)/2,ty=880;
 o.marks.forEach((m,i)=>{const x=tx+i*(T+gap);round(ctx,x,ty,T,T,26);ctx.fillStyle=m?'#2ecc8f':'#1c2944';ctx.fill();
  ctx.fillStyle=m?'#06281a':'#55627a';ctx.font=`900 64px ${FONT}`;ctx.textBaseline='middle';ctx.fillText(m?'✓':'✕',x+T/2,ty+T/2+3);ctx.textBaseline='alphabetic'});
 // Streaks.
 const bits=[];if(o.completion>0)bits.push(`🔥 ${o.completion}-day streak`);if(o.perfect>0)bits.push(`⭐ ${o.perfect} perfect`);
 if(bits.length){ctx.fillStyle='#f7f8fc';ctx.font=`800 40px ${FONT}`;ctx.fillText(bits.join('     '),W/2,1110)}
 // Rank / comparison pill.
 if(o.line){
  ctx.font=`850 36px ${FONT}`;const tw2=Math.min(W-120,ctx.measureText(o.line).width+70),px=(W-tw2)/2,py=1150;
  round(ctx,px,py,tw2,70,35);ctx.fillStyle=css(kit,.2);ctx.fill();ctx.lineWidth=3;ctx.strokeStyle=css(accent,.85);ctx.stroke();
  ctx.fillStyle='#f7f8fc';fit(ctx,o.line,tw2-50,36,850);ctx.textBaseline='middle';ctx.fillText(o.line,W/2,py+36);ctx.textBaseline='alphabetic';
 }
 ctx.fillStyle='#a9b2c4';ctx.font=`700 34px ${FONT}`;ctx.fillText('Can you beat me?  Play free at clubdailyfive.com',W/2,1290);
 return await new Promise(res=>c.toBlob(res,'image/png'));
}
window.CDFShareCard={make};
})();
