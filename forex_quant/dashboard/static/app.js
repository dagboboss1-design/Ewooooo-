const state={symbol:'EUR/USD',timeframe:'M15',refreshTimer:null};
async function loadDashboard(){const statusEl=document.getElementById('connection');try{const [cfg,status]=await Promise.all([fetch('/api/dashboard/config').then(r=>r.json()),fetch('/api/dashboard/status').then(r=>r.json())]);statusEl.textContent=status.market_data_connected?'MARKET FEED KEY CONFIGURED':'LIVE FEED NOT CONNECTED';const tf=document.getElementById('timeframes');tf.innerHTML=cfg.timeframes.map(t=>'<button type="button" class="'+(t===state.timeframe?'active':'')+'" data-tf="'+t+'">'+t+'</button>').join('');tf.addEventListener('click',e=>{const b=e.target.closest('button[data-tf]');if(!b)return;state.timeframe=b.dataset.tf;tf.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));loadCandles();});document.getElementById('chart-symbol').addEventListener('change',e=>{state.symbol=e.target.value;loadCandles();loadDailyBias();});await refreshQuotes();await loadCandles();await loadDailyBias();setInterval(refreshQuotes,15000);setInterval(loadCandles,60000);setInterval(loadDailyBias,300000);}catch(e){statusEl.textContent='DASHBOARD API UNAVAILABLE';}}
async function refreshQuotes(){try{const [cfg,market]=await Promise.all([fetch('/api/dashboard/config').then(r=>r.json()),fetch('/api/market').then(r=>r.json())]);const bySymbol=Object.fromEntries((market.quotes||[]).map(q=>[q.symbol,q]));const unavailable=Object.fromEntries((market.unavailable||[]).map(x=>[typeof x==='string'?x:x.symbol,typeof x==='string'?'Feed not configured':x.reason]));document.getElementById('assets').innerHTML=cfg.assets.map(a=>{const q=bySymbol[a.symbol];if(q){const digits=a.symbol.includes('JPY')?3:(a.symbol==='BTC/USD'?2:a.symbol==='XAU/USD'||a.symbol==='XAG/USD'?2:5);const bid=q.bid==null?'not supplied':Number(q.bid).toFixed(digits);const ask=q.ask==null?'not supplied':Number(q.ask).toFixed(digits);return '<article class="asset"><strong>'+a.label+'</strong><div class="quote">'+Number(q.mid).toFixed(digits)+'</div><small>Bid '+bid+' · Ask '+ask+'</small><small class="live">LIVE · '+String(q.source).toUpperCase()+'</small></article>';}return '<article class="asset"><strong>'+a.label+'</strong><small>'+a.class.toUpperCase()+'</small><small class="unavailable">'+(unavailable[a.symbol]?'Unavailable: '+unavailable[a.symbol]:'Waiting for verified feed')+'</small></article>';}).join('');const live=Object.keys(bySymbol).length;document.getElementById('connection').textContent=live?'LIVE QUOTES · '+live+' INSTRUMENTS':'LIVE FEED NOT CONNECTED';}catch(e){document.getElementById('connection').textContent='QUOTE UPDATE FAILED';}}
function drawCandles(rows){const canvas=document.getElementById('candles'),ctx=canvas.getContext('2d'),rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;canvas.width=Math.max(1,Math.floor(rect.width*dpr));canvas.height=Math.max(1,Math.floor(rect.height*dpr));ctx.scale(dpr,dpr);const w=rect.width,h=rect.height;ctx.clearRect(0,0,w,h);const pad={l:8,r:66,t:14,b:24},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b;ctx.font='10px system-ui';ctx.fillStyle='#8da2bb';ctx.strokeStyle='#1b3550';ctx.lineWidth=1;const highs=rows.map(x=>Number(x.high)),lows=rows.map(x=>Number(x.low));let max=Math.max(...highs),min=Math.min(...lows);if(!Number.isFinite(max)||!Number.isFinite(min)||max<=min){document.getElementById('chart-status').textContent='Invalid candle data';return;}const extra=(max-min)*.07;max+=extra;min-=extra;const y=v=>pad.t+(max-v)/(max-min)*ch;for(let i=0;i<=4;i++){const yy=pad.t+ch*i/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((max-(max-min)*i/4).toFixed(state.symbol.includes('JPY')?3:state.symbol==='BTC/USD'?1:5),w-pad.r+5,yy+3);}const step=cw/rows.length,body=Math.max(2,Math.min(12,step*.62));rows.forEach((c,i)=>{const x=pad.l+i*step+step/2,o=Number(c.open),cl=Number(c.close),hi=Number(c.high),lo=Number(c.low),bull=cl>=o;ctx.strokeStyle=bull?'#19e58a':'#ff657a';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x,y(hi));ctx.lineTo(x,y(lo));ctx.stroke();const top=y(Math.max(o,cl)),height=Math.max(1,Math.abs(y(o)-y(cl)));ctx.fillRect(x-body/2,top,body,height);});const first=rows[0].time,last=rows[rows.length-1].time;ctx.fillStyle='#8da2bb';ctx.fillText(String(first).slice(0,16),pad.l,pad.t+ch+17);ctx.textAlign='right';ctx.fillText(String(last).slice(0,16),w-pad.r,pad.t+ch+17);ctx.textAlign='left';}

async function loadDailyBias(){const value=document.getElementById('daily-bias-value'),detail=document.getElementById('daily-bias-detail');value.textContent='Loading D1…';try{const url='/api/market/candles?symbol='+encodeURIComponent(state.symbol)+'&timeframe=D1&outputsize=80';const r=await fetch(url),d=await r.json();if(!r.ok)throw Error(d.detail||'Daily candles unavailable');const rows=(d.candles||[]).filter(x=>Number.isFinite(Number(x.close)));if(rows.length<25)throw Error('Need at least 25 daily candles for a reliable bias estimate.');const completed=rows.slice(0,-1);const closes=completed.map(x=>Number(x.close));const ema=[];const alpha=2/21;let current=closes[0];for(const close of closes){current=close*alpha+current*(1-alpha);ema.push(current);}const last=closes[closes.length-1],avg=ema[ema.length-1],prior=ema[Math.max(0,ema.length-6)];let bias='NEUTRAL';if(last>avg&&avg>prior)bias='BULLISH';else if(last<avg&&avg<prior)bias='BEARISH';value.textContent=bias;value.dataset.bias=bias.toLowerCase();detail.textContent='Last completed D1 close '+last+' · EMA20 '+avg.toFixed(state.symbol.includes('JPY')?3:5)+' · '+completed.length+' completed bars · '+d.provider.toUpperCase();}catch(e){value.textContent='UNAVAILABLE';value.dataset.bias='neutral';detail.textContent=e.message;}}
let candleRequestId=0;
async function loadCandles(){
const requestId=++candleRequestId;
const requestedSymbol=state.symbol,requestedTimeframe=state.timeframe;
const status=document.getElementById('chart-status');
document.getElementById('chart-title').textContent=requestedSymbol+' · '+requestedTimeframe;
status.textContent='Loading verified candle history…';
try{
const url='/api/market/candles?symbol='+encodeURIComponent(requestedSymbol)+'&timeframe='+encodeURIComponent(requestedTimeframe)+'&outputsize=180';
const res=await fetch(url);
const data=await res.json();
if(requestId!==candleRequestId)return;
if(!res.ok)throw new Error(data.detail||'Candle request failed');
if(!Array.isArray(data.candles)||!data.candles.length)throw new Error('Provider returned no candles for this symbol/timeframe.');
const rows=data.candles.filter(c=>['open','high','low','close'].every(k=>Number.isFinite(Number(c[k]))));
if(!rows.length)throw new Error('Provider returned candles without valid OHLC values.');
rows.sort((a,b)=>String(a.time).localeCompare(String(b.time)));
if(requestId!==candleRequestId)return;
drawCandles(rows);
status.textContent='OHLC candles · '+String(data.provider||'provider').toUpperCase();
document.getElementById('chart-count').textContent=rows.length+' candles';
document.getElementById('chart-updated').textContent='Latest: '+String(rows[rows.length-1].time);
}catch(e){
if(requestId!==candleRequestId)return;
window.lastCandleRows=null;
const canvas=document.getElementById('candles'),ctx=canvas.getContext('2d');
ctx.clearRect(0,0,canvas.width,canvas.height);
status.textContent=e.message;
document.getElementById('chart-count').textContent='No chart data';
document.getElementById('chart-updated').textContent='';
}
}
window.addEventListener('resize',()=>{if(window.lastCandleRows)drawCandles(window.lastCandleRows);});const originalDraw=drawCandles;drawCandles=function(rows){window.lastCandleRows=rows;originalDraw(rows);};
const log=document.getElementById('chat-log'),input=document.getElementById('chat-input'),send=document.getElementById('send-chat'),upload=document.getElementById('chart-upload');let chartData=null;
function addBubble(text,who){const el=document.createElement('div');el.className='chat-bubble '+who;el.textContent=text;log.appendChild(el);log.scrollTop=log.scrollHeight;return el;}
function addJournalAction(bubble,answer){
const side=answer.match(/\b(BUY|SELL)\b/i),entry=answer.match(/(?:entry(?: price)?|entry zone)\s*[:=@-]?\s*([0-9]+(?:\.[0-9]+)?)/i),stop=answer.match(/(?:stop(?: loss)?|SL)\s*[:=@-]?\s*([0-9]+(?:\.[0-9]+)?)/i),target=answer.match(/(?:take profit|target(?:s)?|TP)\s*[:=@-]?\s*([0-9]+(?:\.[0-9]+)?)/i);
if(!side||!entry||!stop||!target){const note=document.createElement('small');note.className='journal-hint';note.textContent='Journal actions appear when the AI provides a clear BUY/SELL setup with entry, stop loss and target.';bubble.appendChild(note);return;}
const actions=document.createElement('div');actions.className='journal-actions';
[['open','＋ Mark as taken · Save'],['skipped','Skip setup · Log']].forEach(([status,label])=>{
const b=document.createElement('button');b.className='journal-save';b.textContent=label;
b.onclick=async()=>{b.disabled=true;b.textContent='Saving…';try{
const r=await fetch('/api/journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:state.symbol,side:side[1].toUpperCase(),timeframe:state.timeframe,entry:Number(entry[1]),stop_loss:Number(stop[1]),take_profit:Number(target[1]),setup_text:answer,source:'ai',status})});
const d=await r.json();if(!r.ok)throw Error(d.detail||'Save failed');b.textContent=status==='open'?'Taken · Saved ✓':'Skipped · Logged ✓';loadJournal();
}catch(e){b.disabled=false;b.textContent='Save failed: '+e.message;}};actions.appendChild(b);});bubble.appendChild(actions);}
async function loadJournal(){const box=document.getElementById('journal-list');try{const r=await fetch('/api/journal'),d=await r.json();if(!r.ok)throw Error(d.detail);document.getElementById('journal-count').textContent=d.count+' trades';document.getElementById('journal-pnl').textContent=Number(d.realized_pnl).toFixed(2);renderJournalAnalytics(d.analytics||{});if(!d.trades.length){box.textContent='No trades recorded yet.';return;}box.innerHTML=d.trades.map(t=>'<article class="journal-trade"><b>'+safe(t.symbol)+' · '+safe(t.side)+'</b><span class="journal-status">'+safe(t.status.toUpperCase())+'</span><small>'+new Date(t.created_at).toLocaleString()+' · '+safe(t.timeframe)+'</small><p>'+safe(t.setup_text)+'</p><small>Entry '+(t.entry??'—')+' · SL '+(t.stop_loss??'—')+' · TP '+(t.take_profit??'—')+'</small>'+(t.status==='open'?'<div class="journal-close"><input type="number" step="any" placeholder="Actual exit" data-exit><input type="number" step="any" placeholder="P/L" data-pnl><button data-close="'+t.trade_id+'">Close trade</button></div>':'<small>Exit '+(t.exit_price??'—')+' · P/L '+(t.pnl??'—')+'</small>')+'</article>').join('');box.querySelectorAll('[data-close]').forEach(b=>b.onclick=async()=>{const c=b.closest('.journal-trade'),exit=c.querySelector('[data-exit]').value,pnl=c.querySelector('[data-pnl]').value;if(!exit){alert('Enter the actual exit price.');return;}const r=await fetch('/api/journal/'+b.dataset.close,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({exit_price:Number(exit),pnl:pnl===''?null:Number(pnl),status:'closed'})});if(r.ok)loadJournal();else alert('Could not close journal record.');});}catch(e){box.textContent='Journal unavailable: '+e.message;}}
function safe(v){return String(v??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
upload.addEventListener('change',()=>{const file=upload.files&&upload.files[0];if(!file){chartData=null;document.getElementById('upload-name').textContent='No chart attached';return;}if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>4*1024*1024){upload.value='';chartData=null;document.getElementById('upload-name').textContent='Use PNG/JPEG/WebP under 4 MB';return;}const reader=new FileReader();reader.onload=()=>{chartData=reader.result;document.getElementById('upload-name').textContent=file.name;};reader.readAsDataURL(file);});
async function sendMessage(){const message=input.value.trim();if(!message&&!chartData)return;addBubble((message||'Please analyse this chart.')+(chartData?' [Chart attached]':''),'user');input.value='';send.disabled=true;send.textContent='Thinking…';const pending=addBubble('Analysing your question…','assistant');try{const res=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:message||'Analyse this chart. Identify instrument/timeframe if visible, market structure, key levels and whether a setup is justified.',chart_image:chartData,symbol:state.symbol,timeframe:state.timeframe})});const data=await res.json();if(!res.ok)throw new Error(data.detail||'AI request failed');pending.textContent=data.answer;const meta=document.createElement('small');meta.className='analysis-meta';meta.textContent='DATA: '+String(data.market_data_status||'unknown').replaceAll('_',' ').toUpperCase()+' · D1 BIAS: '+String(data.daily_bias||'UNAVAILABLE')+' · '+String(data.symbol||state.symbol)+' / '+String(data.timeframe||state.timeframe);pending.appendChild(meta);addJournalAction(pending,data.answer);if('speechSynthesis'in window){const utterance=new SpeechSynthesisUtterance(data.answer);utterance.rate=1;window.speechSynthesis.cancel();window.speechSynthesis.speak(utterance);}chartData=null;upload.value='';document.getElementById('upload-name').textContent='No chart attached';}catch(err){pending.textContent=err.message;}finally{send.disabled=false;send.textContent='Send ↗';log.scrollTop=log.scrollHeight;}}
send.addEventListener('click',sendMessage);input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}});
document.getElementById('voice-input').addEventListener('click',()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){addBubble('Voice input is not supported by this browser. You can still type your question.','assistant');return;}const recognition=new SR();recognition.lang='en-US';recognition.interimResults=false;recognition.onresult=e=>{input.value+=(input.value?' ':'')+e.results[0][0].transcript;input.focus();};recognition.onerror=()=>addBubble('Microphone recognition failed. Check browser microphone permission.','assistant');recognition.start();});
loadDashboard();loadJournal();
function metric(value,suffix=''){return value===null||value===undefined?'—':Number(value).toFixed(2)+suffix;}
function renderJournalAnalytics(a){
const el=document.getElementById('journal-analytics');if(!el)return;
el.innerHTML='<div class="metric"><small>Win rate</small><b>'+metric(a.win_rate_pct,'%')+'</b></div><div class="metric"><small>Average R</small><b>'+metric(a.average_r,'R')+'</b></div><div class="metric"><small>Profit factor</small><b>'+metric(a.profit_factor_r)+'</b></div><div class="metric"><small>Max drawdown</small><b>'+metric(a.max_drawdown_r,'R')+'</b></div><div class="metric"><small>Open trades</small><b>'+Number(a.open_trades||0)+'</b></div><div class="metric"><small>Skipped setups</small><b>'+Number(a.skipped_setups||0)+'</b></div>';
const tf=document.getElementById('journal-timeframes');if(tf){const rows=Object.entries(a.by_timeframe||{});tf.innerHTML=rows.length?'<b>Performance by timeframe</b>'+rows.map(([name,s])=>'<div class="timeframe-row"><span>'+safe(name)+'</span><span>'+s.trades+' scored</span><span>Win '+metric(s.win_rate_pct,'%')+'</span><span>Avg '+metric(s.average_r,'R')+'</span></div>').join(''):'<small>Close trades with entry, stop and exit prices to build timeframe statistics.</small>';}
}


// Interactive chart crosshair: inspect the exact OHLC values of each candle.
(function enableCandleInspection(){
  const canvas=document.getElementById('candles');
  const status=document.getElementById('chart-status');
  if(!canvas||!status)return;
  let baseStatus=status.textContent;
  const redraw=()=>{if(window.lastCandleRows&&window.lastCandleRows.length)drawCandles(window.lastCandleRows);};
  canvas.addEventListener('pointermove',event=>{
    const rows=window.lastCandleRows;
    if(!rows||!rows.length)return;
    const rect=canvas.getBoundingClientRect();
    const pad={l:8,r:66};
    const usable=Math.max(1,rect.width-pad.l-pad.r);
    const x=Math.max(0,Math.min(usable-1,event.clientX-rect.left-pad.l));
    const index=Math.max(0,Math.min(rows.length-1,Math.floor(x/(usable/rows.length))));
    const candle=rows[index];
    redraw();
    const ctx=canvas.getContext('2d');
    const dpr=window.devicePixelRatio||1;
    const px=pad.l+(index+.5)*(usable/rows.length);
    ctx.save();
    ctx.strokeStyle='rgba(151,178,208,.65)';
    ctx.lineWidth=1;
    ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(px,8);ctx.lineTo(px,rect.height-24);ctx.stroke();
    ctx.restore();
    status.textContent=String(candle.time)+' · O '+candle.open+' H '+candle.high+' L '+candle.low+' C '+candle.close;
  });
  canvas.addEventListener('pointerleave',()=>{
    baseStatus=document.getElementById('chart-status').textContent;
    if(window.lastCandleRows&&window.lastCandleRows.length)redraw();
    status.textContent=baseStatus.includes(' · O ')?'OHLC candles · verified provider data':baseStatus;
  });
  const observer=new MutationObserver(()=>{const value=status.textContent;if(!value.includes(' · O '))baseStatus=value;});
  observer.observe(status,{childList:true,characterData:true,subtree:true});
})();
