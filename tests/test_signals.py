import numpy as np
import pandas as pd
import pytest
from forex_quant.signals.indicators import atr, bollinger, classify_regime, rsi
from forex_quant.signals.risk import RiskPolicy

def sample_frame(n=120):
    x=np.arange(n); c=1.10+0.0001*np.sin(x/4)+0.000001*x
    return pd.DataFrame({'time':pd.date_range('2024-01-01',periods=n,freq='h',tz='UTC'),'open':c,'high':c+0.0002,'low':c-0.0002,'close':c})

def test_indicators_align_and_bands_order():
    f=sample_frame(); assert len(atr(f))==len(f); assert len(rsi(f['close']))==len(f)
    m,u,l=bollinger(f['close']); assert u.iloc[-1]>m.iloc[-1]>l.iloc[-1]

def test_regime_label_is_bounded():
    assert classify_regime(sample_frame()) in {'ranging','trending','high_vol','unknown'}

def test_default_risk_is_half_percent():
    assert RiskPolicy().evaluate().effective_risk_fraction==0.005

def test_daily_limit_blocks():
    d=RiskPolicy().evaluate(daily_loss_fraction=0.02); assert not d.approved and d.reason=='daily_loss_limit_reached'

def test_kill_switch_blocks():
    d=RiskPolicy().evaluate(kill_switch=True); assert not d.approved and d.effective_risk_fraction==0

def test_duplicate_timestamps_rejected():
    from forex_quant.signals.strategy import generate_signal
    f=sample_frame(); f.loc[1,'time']=f.loc[0,'time']
    with pytest.raises(ValueError,match='Duplicate'): generate_signal(f,'EUR_USD',10000)
