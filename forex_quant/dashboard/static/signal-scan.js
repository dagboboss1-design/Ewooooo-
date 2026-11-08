(function(){
  const button=document.getElementById('run-scan');
  if(!button)return;
  const field=id=>document.getElementById(id);
  const result=field('scan-result');
  button.addEventListener('click',async()=>{
    const equity=Number(field('scan-equity').value);
    const rate=Number(field('scan-rate').value);
    const daily=Number(field('scan-daily-loss').value);
    const weekly=Number(field('scan-weekly-loss').value);
    const losses=Number(field('scan-losses').value);
    const symbol=field('chart-symbol').value;
    const active=document.querySelector('#timeframes button.active');
    const timeframe=active?active.dataset.tf:'M15';
    if(!Number.isFinite(equity)||equity<=0||!Number.isFinite(rate)||rate<=0){result.textContent='Enter valid account equity and quote-to-account conversion first.';return;}
    if(!Number.isFinite(daily)||daily<0||daily>=100||!Number.isFinite(weekly)||weekly<0||weekly>=100||!Number.isInteger(losses)||losses<0){result.textContent='Check daily/weekly loss percentages and consecutive-loss count.';return;}
    button.disabled=true;button.textContent='Scanning…';result.textContent='Requesting verified candles and checking risk policy…';
    try{
      const response=await fetch('/api/signals/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,timeframe,equity,quote_to_account_rate:rate,daily_loss_fraction:daily/100,weekly_loss_fraction:weekly/100,consecutive_losses:losses})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||'Signal scan failed');
      const lines=['Status: '+String(data.status||'unknown').replaceAll('_',' ').toUpperCase(),'Instrument: '+symbol+' · '+timeframe];
      if(data.completed_candles!==undefined)lines.push('Completed candles analysed: '+data.completed_candles);
      if(data.risk)lines.push('Risk gate: '+(data.risk.approved?'APPROVED':'BLOCKED')+(data.risk.reason?' · '+data.risk.reason:''));
      const signal=(data.signals||[])[0];
      if(signal)lines.push('Setup: '+String(signal.side).toUpperCase(),'Entry: '+signal.entry,'Stop loss: '+signal.stop_loss,'Take profit: '+signal.take_profit,'Units estimate: '+signal.units,'Risk: '+(Number(signal.risk_fraction)*100).toFixed(2)+'%','Confluence score: '+signal.confidence_score+' (not win probability)');
      if(data.alert&&typeof data.alert==='object')lines.push('Alert: '+(data.alert.accepted?'accepted':'not accepted')+' · Telegram '+(data.alert.telegram_sent?'sent':'not sent')+' · Webhook '+(data.alert.webhook_sent?'sent':'not sent'));
      else if(data.alert)lines.push('Alert: '+data.alert);
      lines.push('Broker execution: OFF');
      result.textContent=lines.join('\\n');
      if(signal&&data.risk&&data.risk.approved){
        const actions=document.createElement('div');actions.className='journal-actions';
        const save=document.createElement('button');save.type='button';save.className='journal-save';save.textContent='＋ Mark as taken · Save to Journal';
        save.addEventListener('click',async()=>{
          save.disabled=true;save.textContent='Saving…';
          try{
            const saved=await fetch('/api/journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
              symbol:signal.instrument||symbol,side:String(signal.side).toUpperCase(),timeframe,
              entry:Number(signal.entry),stop_loss:Number(signal.stop_loss),take_profit:Number(signal.take_profit),
              setup_text:'Risk-gated scanner setup. Strategy: '+String(signal.strategy||'baseline')+'. Regime: '+String(signal.regime||'unknown')+'. Confluence score: '+String(signal.confidence_score)+' (not win probability). Invalidation: '+String(signal.invalidation||'—'),
              source:'manual',status:'open'
            })});
            const savedData=await saved.json();if(!saved.ok)throw new Error(savedData.detail||'Journal save failed');
            save.textContent='Taken · Saved to Journal ✓';
          }catch(error){save.disabled=false;save.textContent='Save failed: '+error.message;}
        });
        actions.appendChild(save);result.appendChild(actions);
      }
    }catch(error){result.textContent='Scan unavailable: '+error.message;}
    finally{button.disabled=false;button.textContent='Scan selected market';}
  });
})();
