import struct, lzma
from datetime import date
from forex_quant.providers.dukascopy import decode_bi5

def test_decode_standard_tick_record():
    raw = struct.pack(">IIIff", 125, 108500, 108490, 1.2, 0.8)
    frame = decode_bi5(lzma.compress(raw), "EURUSD", date(2024,1,2), 13)
    assert len(frame) == 1
    assert frame.iloc[0]["ask"] == 1.085
    assert frame.iloc[0]["bid"] == 1.0849
