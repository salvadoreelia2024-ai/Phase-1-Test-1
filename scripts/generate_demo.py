"""Rebuild a deterministic synthetic fixture; never substitutes for live data."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from datetime import datetime,timedelta,timezone
import numpy as np
from engine.snapshot import build_snapshot


def main():
    rng=np.random.default_rng(421)
    prices=97.88*np.exp(np.cumsum(rng.normal(0,.0022,720)))
    prices*=97.88/prices[-1]
    end=datetime(2026,10,23,14,tzinfo=timezone.utc)
    stamps=[(end-timedelta(hours=len(prices)-1-i)).isoformat() for i in range(len(prices))]
    snapshot=build_snapshot(prices.tolist(),stamps,mode='demo')
    snapshot['generatedAt']=end.isoformat()
    target=Path(__file__).resolve().parents[1]/'public/data/snapshot.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(snapshot,separators=(',',':'))+'\n')
    print(f'Wrote synthetic demonstration: {target} ({target.stat().st_size:,} bytes)')
if __name__=='__main__':main()
