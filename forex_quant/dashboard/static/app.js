function formatWAT(value){const d=new Date(value);if(Number.isNaN(d.getTime()))return String(value??'—');return new Intl.DateTimeFormat('en-NG',{timeZone:'Africa/Lagos',dateStyle:'medium',timeStyle:'medium',hour12:false}).format(d)+' WAT';}
function updateWATClock(){const el=document.getElementById('wat-clock');if(el)el.textContent=new Intl.DateTimeFormat('en-NG',{timeZone:'Africa/Lagos',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date())+' WAT';}
// Compact page navigation: keep each tool on its own focused screen.
(function(){
  const links=[...document.querySelectorAll('.bottom-nav a[data-page], .settings-trigger[data-page]')];
  const panels=[...document.querySelectorAll('[data-page]')].filter(el=>!el.matches('.bottom-nav a, .settings-trigger'));
  function show(page){
    panels.forEach(panel=>{panel.hidden=panel.dataset.page!==page;});
    links.forEach(link=>{
      const active=link.dataset.page===page;
      link.classList.toggle('active',active);
      if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
    });
    // The chart is initially fetched while the Markets page is visible and
    // the Signals panel is hidden. Redraw only after the canvas has a layout.
    if(page==='signals'){
      requestAnimationFrame(()=>{
        if(window.lastCandleRows?.length) drawCandles(window.lastCandleRows);
        else if(typeof loadCandles==='function') loadCandles();
      });
    }
  }
  links.forEach(link=>link.addEventListener('click',event=>{
    event.preventDefault();
    show(link.dataset.page);
    history.replaceState(null,'',link.getAttribute('href'));
  }));
  const initial=links.find(link=>link.getAttribute('href')===location.hash)?.dataset.page||'markets';
  show(initial);
})();
function renderAIProviderStatus(status){
 const providers=status.providers||status.ai_provider_health?.providers||{};
 const labels={cloudflare_worker:'Cloudflare Worker',openai:'OpenAI',pollinations:'Pollinations'};
 Object.keys(labels).forEach(key=>{
  const el=document.querySelector('[data-provider="'+key+'"]');if(!el)return;
  const p=providers[key]||{},state=p.state||(p.configured?'not_tested':'not_configured');
  const display={active:'ACTIVE NOW',checking:'CHECKING…',unavailable:'FAILED · '+(p.detail||'Provider unavailable'),not_tested:'KEY SET · NOT TESTED',not_configured:'NOT CONFIGURED'};
  el.textContent=display[state]||String(state).replaceAll('_',' ').toUpperCase();
  el.dataset.state=state;
  el.title=p.detail||labels[key];
 });
 const offline=document.querySelector('[data-provider="offline"]');if(offline){offline.textContent='EDUCATIONAL FALLBACK';offline.dataset.state='fallback';}
 const active=status.active_provider||status.ai_provider_health?.active_provider;
 const configured=Object.keys(labels).find(k=>providers[k]?.configured||status.ai_providers?.[k]);
 const pill=document.getElementById('ai-status-pill');
 if(pill)pill.textContent=active?'ACTIVE · '+active.replaceAll('_',' ').toUpperCase():configured?'KEY SET · NOT VERIFIED':'AI OFFLINE · NO PROVIDER';
}
async function refreshAIProviderStatus(){
 try{const r=await fetch('/api/ai/status');if(!r.ok)throw Error('status unavailable');renderAIProviderStatus(await r.json());}
 catch(e){const pill=document.getElementById('ai-status-pill');if(pill)pill.textContent='AI STATUS UNAVAILABLE';}
}
function updateAIProviderStatus(data){
 const diagnostics=data.provider_diagnostics||{};
 if(diagnostics.providers)renderAIProviderStatus(diagnostics);
 else{
  const active=String(data.provider||data.assistant_mode||'offline');
  const pill=document.getElementById('ai-status-pill');if(pill)pill.textContent=active==='offline'?'AI OFFLINE · EDUCATIONAL MODE':'ACTIVE · '+active.replaceAll('_',' ').toUpperCase();
  document.querySelectorAll('[data-provider]').forEach(el=>{if(el.dataset.provider===active){el.textContent='ACTIVE NOW';el.dataset.state='active';}});
 }
 refreshAIProviderStatus();
}
const state={symbol:'EUR/USD',timeframe:'M15',refreshTimer:null};
async function loadDashboard(){updateWATClock();setInterval(updateWATClock,1000);const statusEl=document.getElementById('connection');try{const [cfg,status]=await Promise.all([fetch('/api/dashboard/config').then(r=>r.json()),fetch('/api/dashboard/status').then(r=>r.json())]);statusEl.textContent=status.market_data_connected?'LIVE PROVIDER KEY CONFIGURED':(status.historical_data_available?'HISTORICAL ARCHIVE · NO LIVE QUOTES':'LIVE FEED NOT CONNECTED');const feed=document.getElementById('settings-feed');if(feed)feed.textContent=status.market_data_connected?'Live provider configured':(status.historical_data_available?'Dukascopy historical only':'Not connected');const ai=document.getElementById('settings-ai');if(ai)ai.textContent=status.ai_provider_configured||'offline';renderAIProviderStatus(status);refreshAIProviderStatus();const tf=document.getElementById('timeframes');tf.innerHTML=cfg.timeframes.map(t=>'<button type="button" class="'+(t===state.timeframe?'active':'')+'" data-tf="'+t+'">'+t+'</button>').join('');tf.addEventListener('click',e=>{const b=e.target.closest('button[data-tf]');if(!b)return;state.timeframe=b.dataset.tf;tf.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));loadCandles();});document.getElementById('chart-symbol').addEventListener('change',e=>{state.symbol=e.target.value;loadCandles();loadDailyBias();});await refreshQuotes();await loadCandles();await loadDailyBias();setInterval(refreshQuotes,1800000);if(state.refreshTimer)clearInterval(state.refreshTimer);state.refreshTimer=setInterval(loadCandles,30000);setInterval(loadDailyBias,21600000);}catch(e){statusEl.textContent='DASHBOARD API UNAVAILABLE';}}
async function refreshQuotes(){try{const [cfg,market]=await Promise.all([fetch('/api/dashboard/config').then(r=>r.json()),fetch('/api/market').then(r=>r.json())]);const bySymbol=Object.fromEntries((market.quotes||[]).map(q=>[String(q.symbol||'').replace(/_/g,'/'),q]));const unavailable=Object.fromEntries((market.unavailable||[]).map(x=>[typeof x==='string'?x:x.symbol,typeof x==='string'?'Feed not configured':x.reason]));document.getElementById('assets').innerHTML=cfg.assets.map(a=>{const q=bySymbol[a.symbol];if(q){const digits=a.symbol.includes('JPY')?3:(a.symbol==='BTC/USD'?2:a.symbol==='XAU/USD'||a.symbol==='XAG/USD'?2:5);const bid=q.bid==null?'not supplied':Number(q.bid).toFixed(digits);const ask=q.ask==null?'not supplied':Number(q.ask).toFixed(digits);return '<article class="asset"><strong>'+a.label+'</strong><div class="quote">'+Number(q.mid).toFixed(digits)+'</div><small>Bid '+bid+' · Ask '+ask+'</small><small class="live">PROVIDER DATA · '+String(q.source).toUpperCase()+'</small></article>';}return '<article class="asset"><strong>'+a.label+'</strong><small>'+a.class.toUpperCase()+'</small><small class="unavailable">'+(unavailable[a.symbol]?'Unavailable: '+unavailable[a.symbol]:'Waiting for verified feed')+'</small></article>';}).join('');const live=Object.keys(bySymbol).length;document.getElementById('connection').textContent=live?'CACHED PROVIDER QUOTES · '+live+' INSTRUMENTS':'LIVE FEED NOT CONNECTED';}catch(e){document.getElementById('connection').textContent='QUOTE UPDATE FAILED';}}
function drawCandles(rows) {
  requestAnimationFrame(() => drawCandlesPlotly(rows));
}

function drawCandlesPlotly(rows) {
  const el = document.getElementById('candles');
  if (!el) return;
  if (!window.Plotly) {
    el.textContent = 'Chart library unavailable. Check the network connection and reload.';
    return;
  }
  if (!Array.isArray(rows) || !rows.length) {
    el.innerHTML = '<div style="padding:24px;color:#888;text-align:center;">No verified candles available — WAIT.</div>';
    return;
  }
  const validRows = rows.filter(r => r && r.time != null &&
    ['open','high','low','close'].every(k => Number.isFinite(Number(r[k]))));
  if (!validRows.length) {
    el.innerHTML = '<div style="padding:24px;color:#888;text-align:center;">No valid OHLC candles available — WAIT.</div>';
    return;
  }
  const times=validRows.map(r=>r.time), opens=validRows.map(r=>Number(r.open));
  const highs=validRows.map(r=>Number(r.high)), lows=validRows.map(r=>Number(r.low));
  const closes=validRows.map(r=>Number(r.close));
  const volumes=validRows.map(r=>Number.isFinite(Number(r.volume))?Number(r.volume):0);
  function ema(values,period){
    const k=2/(period+1);let prev=values[0];const out=[prev];
    for(let i=1;i<values.length;i++){prev=values[i]*k+prev*(1-k);out.push(prev);}
    return out;
  }
  function bollinger(values,period=20,mult=2){
    const up=[],mid=[],lo=[];
    for(let i=0;i<values.length;i++){
      if(i<period-1){up.push(null);mid.push(null);lo.push(null);continue;}
      const windowValues=values.slice(i-period+1,i+1);
      const mean=windowValues.reduce((x,y)=>x+y,0)/period;
      const variance=windowValues.reduce((x,y)=>x+(y-mean)**2,0)/period;
      const sd=Math.sqrt(variance);mid.push(mean);up.push(mean+mult*sd);lo.push(mean-mult*sd);
    }
    return {up,mid,lo};
  }
  const ema20=ema(closes,20),ema50=ema(closes,50),bb=bollinger(closes,20,2);
  const barColors=closes.map((c,i)=>c>=opens[i]?'#00d47e':'#ff4d4d');
  const traces=[
    {type:'candlestick',x:times,open:opens,high:highs,low:lows,close:closes,name:'Price',
      increasing:{line:{color:'#00d47e'},fillcolor:'#00d47e'},
      decreasing:{line:{color:'#ff4d4d'},fillcolor:'#ff4d4d'},yaxis:'y'},
    {type:'scatter',mode:'lines',x:times,y:ema20,name:'EMA20',line:{color:'#4da3ff',width:1},yaxis:'y',hoverinfo:'skip'},
    {type:'scatter',mode:'lines',x:times,y:ema50,name:'EMA50',line:{color:'#ffaa33',width:1},yaxis:'y',hoverinfo:'skip'},
    {type:'scatter',mode:'lines',x:times,y:bb.up,name:'BB Upper',line:{color:'#777',width:1,dash:'dot'},yaxis:'y',hoverinfo:'skip'},
    {type:'scatter',mode:'lines',x:times,y:bb.lo,name:'BB Lower',line:{color:'#777',width:1,dash:'dot'},
      fill:'tonexty',fillcolor:'rgba(120,120,120,0.05)',yaxis:'y',hoverinfo:'skip'},
    {type:'bar',x:times,y:volumes,name:'Volume',marker:{color:barColors},yaxis:'y2',hoverinfo:'skip'}
  ];
  const layout={
    template:'plotly_dark',autosize:true,height:500,margin:{l:58,r:18,t:42,b:42},showlegend:true,
    legend:{orientation:'h',y:1.12,x:0,bgcolor:'rgba(0,0,0,0)'},
    xaxis:{rangeslider:{visible:false},gridcolor:'rgba(255,255,255,0.05)',automargin:true},
    yaxis:{gridcolor:'rgba(255,255,255,0.05)',domain:[0.28,1],automargin:true},
    yaxis2:{gridcolor:'rgba(255,255,255,0.05)',domain:[0,0.22],automargin:true},
    uirevision:state.symbol+':'+state.timeframe,
    paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)'
  };
  Plotly.react(el,traces,layout,{responsive:true,displayModeBar:false});
}

async function loadDailyBias(){const value=document.getElementById('daily-bias-value'),detail=document.getElementById('daily-bias-detail');value.textContent='Loading D1…';try{const url='/api/market/candles?symbol='+encodeURIComponent(state.symbol)+'&timeframe=D1&outputsize=80';const r=await fetch(url),d=await r.json();if(!r.ok)throw Error(d.detail||'Daily candles unavailable');const rows=(d.candles||[]).filter(x=>Number.isFinite(Number(x.close)));if(rows.length<25)throw Error('Need at least 25 daily candles for a reliable bias estimate.');const completed=rows.slice(0,-1);const closes=completed.map(x=>Number(x.close));const ema=[];const alpha=2/21;let current=closes[0];for(const close of closes){current=close*alpha+current*(1-alpha);ema.push(current);}const last=closes[closes.length-1],avg=ema[ema.length-1],prior=ema[Math.max(0,ema.length-6)];let bias='NEUTRAL';if(last>avg&&avg>prior)bias='BULLISH';else if(last<avg&&avg<prior)bias='BEARISH';value.textContent=bias;value.dataset.bias=bias.toLowerCase();detail.textContent='Last completed D1 close '+last+' · EMA20 '+avg.toFixed(state.symbol.includes('JPY')?3:5)+' · '+completed.length+' completed bars · '+d.provider.toUpperCase();}catch(e){value.textContent='UNAVAILABLE';value.dataset.bias='neutral';detail.textContent=e.message;}}
async function loadTechnicalAnalysis(symbol=state.symbol,timeframe=state.timeframe){
 const signal=document.getElementById('technical-signal');
 const bias=document.getElementById('technical-bias');
 const votes=document.getElementById('technical-votes');
 const plan=document.getElementById('technical-plan');
 const source=document.getElementById('technical-source');
 const indicators=document.getElementById('technical-indicators');
 const notes=document.getElementById('technical-notes');
 if(!signal)return;
 signal.textContent='CHECKING…';source.textContent='VERIFYING PROVIDER DATA';
 try{
  const url='/api/analysis/technical?symbol='+encodeURIComponent(symbol)+'&timeframe='+encodeURIComponent(timeframe);
  const response=await fetch(url),data=await response.json();
  if(!response.ok)throw Error(data.detail||'Technical analysis unavailable');
  signal.textContent=data.signal||'HOLD / NO TRADE';
  signal.dataset.signal=(data.signal||'hold').toLowerCase().replaceAll(' ','-');
  bias.textContent='Bias · '+(data.bias||'Neutral');
  votes.textContent=(data.votes||'—')+' · '+data.candles_used+' candles';
  source.textContent=(data.data_status==='historical_backup_not_live'?'HISTORICAL BACKUP · NOT LIVE':String(data.provider||'PROVIDER').toUpperCase())+' · '+timeframe;
  const p=data.plan;
  plan.textContent=p?'Entry '+p.entry+' · Stop '+p.stop+' · Target '+p.target+' · RR 1:2':'No entry plan · confluence threshold not met';
  const i=data.indicators||{};
  indicators.textContent='RSI '+(i.rsi??'—')+' · ATR '+(i.atr??'—')+' · EMA20 '+(i.ema20??'—')+' · EMA50 '+(i.ema50??'—')+' · Volume '+(i.vol_ratio==null?'not available':i.vol_ratio+'x');
  notes.replaceChildren(...(data.notes||[]).map(note=>{const li=document.createElement('li');li.textContent=note;return li;}));
 }catch(error){
  signal.textContent='WAIT / UNAVAILABLE';signal.dataset.signal='wait';
  bias.textContent='Bias · Unconfirmed';votes.textContent='No verified analysis';
  plan.textContent=error.message;source.textContent='NO VERIFIED ANALYSIS';
  indicators.textContent='Indicators unavailable';
  notes.replaceChildren();
 }
}

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
status.textContent=(data.data_status==='historical_backup_not_live'?'HISTORICAL BACKUP · NOT LIVE':'PRIMARY FEED · '+String(data.provider||'provider').toUpperCase());
document.getElementById('chart-count').textContent=rows.length+' candles';
document.getElementById('chart-updated').textContent='Latest: '+formatWAT(rows[rows.length-1].time);
await loadTechnicalAnalysis(requestedSymbol,requestedTimeframe);
}catch(e){
if(requestId!==candleRequestId)return;
window.lastCandleRows=null;
const chart=document.getElementById('candles');
  if(chart) chart.innerHTML='<div style="padding:24px;color:#888;text-align:center;">Chart unavailable: '+safe(e.message)+'</div>';
status.textContent=e.message;
document.getElementById('chart-count').textContent='No chart data';
document.getElementById('chart-updated').textContent='';
}
}
window.addEventListener('resize',()=>{if(window.lastCandleRows)drawCandles(window.lastCandleRows);});const originalDraw=drawCandles;drawCandles=function(rows){window.lastCandleRows=rows;originalDraw(rows);};
const log=document.getElementById('chat-log'),input=document.getElementById('chat-input'),send=document.getElementById('send-chat'),upload=document.getElementById('chart-upload');let chartData=null;
function addBubble(text,who){const el=document.createElement('div');el.className='chat-bubble '+who;el.textContent=text;log.appendChild(el);log.scrollTop=log.scrollHeight;return el;}
function appendAIDiagnostics(bubble,data){
 if(data.assistant_mode!=='offline')return;
 const providers=data.provider_diagnostics?.providers||{};
 const labels={cloudflare_worker:'Cloudflare Worker',openai:'OpenAI',pollinations:'Pollinations'};
 const issues=Object.entries(providers)
  .filter(([,p])=>p.state==='unavailable'||p.state==='not_configured')
  .map(([name,p])=>(labels[name]||name)+': '+(p.detail||p.state));
 if(!issues.length)return;
 const note=document.createElement('small');note.className='analysis-meta';
 note.textContent='AI CONNECTION DIAGNOSTIC · '+issues.join(' · ');
 bubble.appendChild(note);
}
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
async function loadJournal(){const box=document.getElementById('journal-list');try{const r=await fetch('/api/journal'),d=await r.json();if(!r.ok)throw Error(d.detail);document.getElementById('journal-count').textContent=d.count+' trades';document.getElementById('journal-pnl').textContent=Number(d.realized_pnl).toFixed(2);renderJournalAnalytics(d.analytics||{});if(!d.trades.length){box.textContent='No trades recorded yet.';return;}box.innerHTML=d.trades.map(t=>'<article class="journal-trade"><b>'+safe(t.symbol)+' · '+safe(t.side)+'</b><span class="journal-status">'+safe(t.status.toUpperCase())+'</span><small>'+formatWAT(t.created_at)+' · '+safe(t.timeframe)+'</small><p>'+safe(t.setup_text)+'</p><small>Entry '+(t.entry??'—')+' · SL '+(t.stop_loss??'—')+' · TP '+(t.take_profit??'—')+'</small>'+(t.status==='open'?'<div class="journal-close"><input type="number" step="any" placeholder="Actual exit" data-exit><input type="number" step="any" placeholder="P/L" data-pnl><button data-close="'+t.trade_id+'">Close trade</button></div>':'<small>Exit '+(t.exit_price??'—')+' · P/L '+(t.pnl??'—')+'</small>')+'</article>').join('');box.querySelectorAll('[data-close]').forEach(b=>b.onclick=async()=>{const c=b.closest('.journal-trade'),exit=c.querySelector('[data-exit]').value,pnl=c.querySelector('[data-pnl]').value;if(!exit){alert('Enter the actual exit price.');return;}const r=await fetch('/api/journal/'+b.dataset.close,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({exit_price:Number(exit),pnl:pnl===''?null:Number(pnl),status:'closed'})});if(r.ok)loadJournal();else alert('Could not close journal record.');});}catch(e){box.textContent='Journal unavailable: '+e.message;}}
function safe(v){return String(v??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
upload.addEventListener('change',()=>{const file=upload.files&&upload.files[0];if(!file){chartData=null;document.getElementById('upload-name').textContent='No chart attached';return;}if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>4*1024*1024){upload.value='';chartData=null;document.getElementById('upload-name').textContent='Use PNG/JPEG/WebP under 4 MB';return;}const reader=new FileReader();reader.onload=()=>{chartData=reader.result;document.getElementById('upload-name').textContent=file.name;};reader.readAsDataURL(file);});
async function sendMessage(){const message=input.value.trim();if(!message&&!chartData)return;addBubble((message||'Please analyse this chart.')+(chartData?' [Chart attached]':''),'user');input.value='';send.disabled=true;send.textContent='Thinking…';const pending=addBubble('Analysing your question…','assistant');try{const res=await fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:message||'Analyse this chart. Identify instrument/timeframe if visible, market structure, key levels and whether a setup is justified.',chart_image:chartData,symbol:state.symbol,timeframe:state.timeframe})});const data=await res.json();if(!res.ok)throw new Error(data.detail||'AI request failed');pending.textContent=data.answer;updateAIProviderStatus(data);appendAIDiagnostics(pending,data);const meta=document.createElement('small');meta.className='analysis-meta';meta.textContent=String(data.assistant_mode||'unknown').replaceAll('_',' ').toUpperCase()+' · DATA: '+String(data.market_data_status||'unknown').replaceAll('_',' ').toUpperCase()+' · D1 BIAS: '+String(data.daily_bias||'UNAVAILABLE')+' · '+String(data.symbol||state.symbol)+' / '+String(data.timeframe||state.timeframe);pending.appendChild(meta);addJournalAction(pending,data.answer);if('speechSynthesis'in window){const utterance=new SpeechSynthesisUtterance(data.answer);utterance.rate=1;window.speechSynthesis.cancel();window.speechSynthesis.speak(utterance);}chartData=null;upload.value='';document.getElementById('upload-name').textContent='No chart attached';}catch(err){pending.textContent=err.message;}finally{send.disabled=false;send.textContent='Send ↗';log.scrollTop=log.scrollHeight;}}
send.addEventListener('click',sendMessage);input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}});
document.getElementById('voice-input').addEventListener('click',()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){addBubble('Voice input is not supported by this browser. You can still type your question.','assistant');return;}const recognition=new SR();recognition.lang='en-US';recognition.interimResults=false;recognition.onresult=e=>{input.value+=(input.value?' ':'')+e.results[0][0].transcript;input.focus();};recognition.onerror=()=>addBubble('Microphone recognition failed. Check browser microphone permission.','assistant');recognition.start();});
loadDashboard();loadJournal();loadNews();
setInterval(loadNews,60000);
function metric(value,suffix=''){return value===null||value===undefined?'—':Number(value).toFixed(2)+suffix;}
function renderJournalAnalytics(a){
const el=document.getElementById('journal-analytics');if(!el)return;
el.innerHTML='<div class="metric"><small>Win rate</small><b>'+metric(a.win_rate_pct,'%')+'</b></div><div class="metric"><small>Average R</small><b>'+metric(a.average_r,'R')+'</b></div><div class="metric"><small>Profit factor</small><b>'+metric(a.profit_factor_r)+'</b></div><div class="metric"><small>Max drawdown</small><b>'+metric(a.max_drawdown_r,'R')+'</b></div><div class="metric"><small>Open trades</small><b>'+Number(a.open_trades||0)+'</b></div><div class="metric"><small>Skipped setups</small><b>'+Number(a.skipped_setups||0)+'</b></div>';
const tf=document.getElementById('journal-timeframes');if(tf){const rows=Object.entries(a.by_timeframe||{});tf.innerHTML=rows.length?'<b>Performance by timeframe</b>'+rows.map(([name,s])=>'<div class="timeframe-row"><span>'+safe(name)+'</span><span>'+s.trades+' scored</span><span>Win '+metric(s.win_rate_pct,'%')+'</span><span>Avg '+metric(s.average_r,'R')+'</span></div>').join(''):'<small>Close trades with entry, stop and exit prices to build timeframe statistics.</small>';}
}


// Plotly provides native OHLC hover inspection; canvas handlers are not required.\n\nlet spikeEventTimestamp = null;
function updateSpikeCountdown(){
 const countdown=document.getElementById('spike-countdown');if(!countdown)return;
 if(!spikeEventTimestamp){return;}
 const seconds=Math.max(0,Math.floor((spikeEventTimestamp-Date.now())/1000));
 if(seconds===0){countdown.textContent='RELEASE TIME';return;}
 const h=String(Math.floor(seconds/3600)).padStart(2,'0');
 const m=String(Math.floor((seconds%3600)/60)).padStart(2,'0');
 const s=String(seconds%60).padStart(2,'0');
 countdown.textContent=h+':'+m+':'+s;
}
function renderSpikeIntelligence(spike){
 const countdown=document.getElementById('spike-countdown');
 const direction=document.getElementById('spike-direction');
 const eventName=document.getElementById('spike-event-name');
 const instrument=document.getElementById('spike-instrument');
 if(!countdown||!direction||!eventName||!instrument)return;
 const status=spike?.status||'unavailable';
 spikeEventTimestamp=spike?.event_time?Date.parse(spike.event_time):null;
 if(status==='no_upcoming_event'||!spikeEventTimestamp||Number.isNaN(spikeEventTimestamp)){
  countdown.textContent='NO UPCOMING NEWS';direction.textContent='WAIT';eventName.textContent='Calendar event not available';instrument.textContent='No active forecast';spikeEventTimestamp=null;return;
 }
 updateSpikeCountdown();
 eventName.textContent=(spike.event_title||'High-impact news')+' · '+(spike.currency||'');
 direction.textContent=(status==='forecast_ready'?(spike.direction||'WAIT'):'WAIT');
 direction.dataset.direction=direction.textContent.toLowerCase();
 instrument.textContent=spike.instrument|| (status==='countdown'?'Forecast starts at T-15:00':'Awaiting verified market data');
}
setInterval(updateSpikeCountdown,1000);

async function loadNews(){
 const status=document.getElementById('news-status');
 const events=document.getElementById('news-events');
 const headlines=document.getElementById('news-headlines');
 if(!status||!events||!headlines)return;
 try{
  const response=await fetch('/api/news');
  const data=await response.json();
  renderSpikeIntelligence(data.spike_intelligence);
  if(!response.ok)throw Error(data.detail||'News request failed');
  status.textContent=data.status==='live'?'Provider updates received · Calendar: '+data.calendar_status+' · Headlines: '+data.headlines_status:'News providers unavailable · No events or headlines are being invented.';
  events.innerHTML=(data.events||[]).length?(data.events||[]).map(e=>'<article class="news-item"><b>'+safe(e.title||'Untitled event')+'</b><small>'+safe(e.event_time||'Time not supplied')+' · '+safe(e.country||e.currency||'')+' · '+safe(e.importance||'')+'</small><small>Actual '+safe(e.actual??'—')+' · Forecast '+safe(e.forecast??'—')+' · Previous '+safe(e.previous??'—')+'</small></article>').join(''):'<div class="empty-state">No calendar events returned.</div>';
  headlines.innerHTML=(data.headlines||[]).length?(data.headlines||[]).map(a=>{const url=String(a.url||'');const safeUrl=/^https?:\/\//i.test(url)?url:'#';return '<article class="news-item"><b><a href="'+safe(safeUrl)+'" target="_blank" rel="noopener noreferrer">'+safe(a.title||'Untitled headline')+'</a></b><small>'+safe(a.published_at||'Time not supplied')+' · '+safe(a.domain||a.source_country||'GDELT')+'</small></article>';}).join(''):'<div class="empty-state">No recent headlines returned.</div>';
 }catch(error){
  status.textContent='News unavailable: '+error.message+' · No sample events are shown.';
  events.innerHTML='<div class="empty-state">Calendar feed unavailable.</div>';
  headlines.innerHTML='<div class="empty-state">Headline feed unavailable.</div>';
 }
}

async function loadPaperAccount(){
 const status=document.getElementById('paper-account-status');if(!status)return;
 try{
  const [ar,pr]=await Promise.all([fetch('/api/paper/account'),fetch('/api/paper/positions')]);
  const account=await ar.json(),positions=await pr.json();
  if(account.configured&&account.account){
   const a=account.account;
   document.getElementById('paper-balance').value=a.starting_balance;
   document.getElementById('paper-order-balance').value=a.starting_balance;
   document.getElementById('paper-currency').value=a.currency;
   document.getElementById('paper-spread').value=a.spread;
   document.getElementById('paper-slippage').value=a.slippage;
   document.getElementById('paper-commission').value=a.commission_per_unit;
   document.getElementById('paper-contracts').value=JSON.stringify(a.contract_specs,null,2);
   status.textContent='Paper account configured · '+a.currency+' · simulation only.';const orderButton=document.getElementById('submit-paper-order');if(orderButton)orderButton.disabled=false;
  }else {status.textContent='Not configured. Enter your own account values; no balance or contract size is assumed.';const orderButton=document.getElementById('submit-paper-order');if(orderButton)orderButton.disabled=true;}
  const box=document.getElementById('paper-positions');
  box.innerHTML=(positions.positions||[]).length?(positions.positions||[]).map(p=>'<article class="journal-trade"><b>'+safe(p.symbol)+' · '+safe(p.side)+'</b><small>Entry '+p.entry+' · Remaining quantity '+(JSON.parse(p.setup_text||'{}').remaining_quantity??JSON.parse(p.setup_text||'{}').quantity_units??'—')+'</small><div class="journal-close"><input type="number" step="any" min="0.00000001" placeholder="Verified mark price" data-mark><input type="number" step="any" min="0.00000001" placeholder="Close quantity" data-pqty><input type="number" step="any" min="0.00000001" placeholder="Exit price" data-pexit><button data-pclose="'+p.trade_id+'">Partial / full close</button></div></article>').join(''):'<small>No open paper positions.</small>';
  box.querySelectorAll('[data-pclose]').forEach(button=>button.onclick=async()=>{
   const card=button.closest('.journal-trade'),quantity=Number(card.querySelector('[data-pqty]').value),exit_price=Number(card.querySelector('[data-pexit]').value);
   if(!(quantity>0&&exit_price>0)){alert('Enter a positive quantity and simulated exit price.');return;}
   button.disabled=true;try{const r=await fetch('/api/paper/positions/'+button.dataset.pclose+'/partial-close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quantity,exit_price})});const d=await r.json();if(!r.ok)throw Error(d.detail||'Close rejected');loadPaperAccount();loadJournal();}catch(e){alert(e.message);button.disabled=false;}
  });
 }catch(e){status.textContent='Paper account unavailable: '+e.message;}
}
document.getElementById('save-paper-account')?.addEventListener('click',async()=>{
 const status=document.getElementById('paper-account-status');
 try{
  const contract_specs=JSON.parse(document.getElementById('paper-contracts').value||'{}');
  const payload={starting_balance:Number(document.getElementById('paper-balance').value),currency:document.getElementById('paper-currency').value,spread:Number(document.getElementById('paper-spread').value),slippage:Number(document.getElementById('paper-slippage').value),commission_per_unit:Number(document.getElementById('paper-commission').value),contract_specs};
  const r=await fetch('/api/paper/account',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();
  if(!r.ok)throw Error(d.detail||'Account settings rejected');
  status.textContent='Paper account saved · '+d.account.currency+' · live execution remains OFF.';
  loadPaperAccount();
 }catch(e){status.textContent='Could not save paper account: '+e.message;}
});
loadPaperAccount();

document.getElementById('refresh-paper-equity')?.addEventListener('click',async()=>{
 const box=document.getElementById('paper-equity');
 try{
  const marks={};
  document.querySelectorAll('#paper-positions [data-mark]').forEach(input=>{
   const card=input.closest('.journal-trade'),value=Number(input.value);
   if(value>0)marks[card.querySelector('[data-pclose]').dataset.pclose]=value;
  });
  const r=await fetch('/api/paper/account/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({marks})});
  const d=await r.json();if(!r.ok)throw Error(d.detail||'Snapshot unavailable');
  box.textContent='Starting '+d.currency+' '+d.starting_balance.toFixed(2)+' · Realized '+d.realized_pnl.toFixed(2)+' · Unrealized '+d.unrealized_pnl.toFixed(2)+' · Fees '+d.fees.toFixed(2)+' · Equity '+d.equity.toFixed(2)+' · Open '+d.open_positions+' · PAPER ONLY';
 }catch(e){box.textContent='Equity not calculated: '+e.message;}
});

document.getElementById('run-paper-reconcile')?.addEventListener('click',async()=>{
 const status=document.getElementById('paper-reconcile-status');status.textContent='Checking saved paper records…';
 try{const r=await fetch('/api/paper/reconcile'),d=await r.json();if(!r.ok)throw Error(d.detail||'Reconciliation failed');status.textContent=d.status.toUpperCase()+' · '+d.checked_paper_records+' records checked · '+d.discrepancies.length+' discrepancies · internal paper ledger only.';}catch(e){status.textContent='Reconciliation unavailable: '+e.message;}
});

document.getElementById('submit-paper-order')?.addEventListener('click',async()=>{
 const status=document.getElementById('paper-order-status'),button=document.getElementById('submit-paper-order');
 const value=id=>Number(document.getElementById(id).value);
 const payload={symbol:document.getElementById('paper-order-symbol').value,side:document.getElementById('paper-order-side').value,timeframe:document.getElementById('paper-order-timeframe').value,entry:value('paper-order-entry'),stop_loss:value('paper-order-stop'),take_profit:value('paper-order-target'),account_balance:value('paper-order-balance'),daily_loss_fraction:value('paper-order-daily')/100,weekly_loss_fraction:value('paper-order-weekly')/100,consecutive_losses:value('paper-order-losses'),kill_switch:document.getElementById('paper-order-kill').checked};
 if(!payload.entry||!payload.stop_loss||!payload.take_profit||!payload.account_balance){status.textContent='Enter a positive entry, stop, target and account equity.';return;}
 button.disabled=true;status.textContent='Checking risk gates and simulating fill…';
 try{const r=await fetch('/api/paper/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:(d.detail?.reason||JSON.stringify(d.detail)||'Paper order rejected'));status.textContent='PAPER FILLED · '+d.paper_order.side+' '+d.paper_order.symbol+' · Entry fill '+d.simulated_entry_fill+' · Quantity '+d.paper_order.units+' generic units · risk '+d.paper_order.risk_amount+' · no broker order sent.';loadPaperAccount();loadJournal();}catch(e){status.textContent='Paper order not placed: '+e.message;}finally{button.disabled=false;}
});
