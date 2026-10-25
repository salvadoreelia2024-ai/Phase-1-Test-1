"""Publishable JSON tables; browsers only select rows, never rerun the model."""
import hashlib
import json
from datetime import datetime, timezone
import numpy as np
from .model import ANNUAL_HOURS, fit_volatility, trading_hours, time_grid, simulate

WINDOWS = [('1h','1 hour',1),('3h','3 hours',3),('6h','6 hours',6),('12h','12 hours',12),('1d','1 day',24),('3d','3 days',72),('1w','1 week',168),('2w','2 weeks',336),('1mo','1 month',720),('3mo','3 months',2160)]


def build_snapshot(prices, timestamps, *, mode='live', paths=12000, seed=1729, nasdaq=None, brent_spread=None, previous=None):
    if len(prices) != len(timestamps):
        raise ValueError('Prices and timestamps must have matching lengths')
    if mode not in ('demo','live') or not 500 <= paths <= 100000:
        raise ValueError('Invalid mode or path count')
    parsed = [datetime.fromisoformat(t.replace('Z','+00:00')) for t in timestamps]
    if any(t.tzinfo is None for t in parsed) or any(a >= b for a,b in zip(parsed,parsed[1:])):
        raise ValueError('Timestamps must increase and include timezone')
    sigma, fitted = fit_volatility(prices)
    reference = float(np.average(prices[-4:],weights=[1,2,3,4]))
    if previous and previous.get('mode') == mode:
        old = previous['referencePrice']
        if abs(reference-old) < old*sigma*.25:
            reference = old
    reference = round(reference,4)
    center = round(reference*2)/2
    levels = np.array([round(center+i*.5,2) for i in range(-30,31) if center+i*.5>0])
    hours = [trading_hours(parsed[-1],w[2]) for w in WINDOWS]
    grid = time_grid(hours)
    logp, maximum, minimum = simulate(reference,sigma,grid,paths,seed)
    thresholds = np.log(levels/reference)
    # First crossing bin; zero means already at the barrier; infinity means no hit.
    first = np.full((len(levels),paths),np.inf)
    for i,threshold in enumerate(thresholds):
        crosses = maximum >= threshold if threshold >= 0 else minimum <= threshold
        first[i] = np.where(crosses.any(axis=1),np.argmax(crosses,axis=1),np.inf)
    # Bootstrap realized-return scale. Conditional sensitivity, not a fitted
    # event/GARCH posterior and never advertised as an 80% confidence interval.
    returns = np.diff(np.log(prices))[-120:]
    rng = np.random.default_rng(seed+1)
    scales = np.std(rng.choice(returns,size=(31,len(returns)),replace=True),axis=1)/max(np.std(returns),1e-9)
    scales = np.clip(scales,.7,1.4)
    horizons=[]
    for (wid,label,calendar),hours_i in zip(WINDOWS,hours):
        end = int(np.searchsorted(grid,hours_i))
        select = np.unique(np.r_[np.linspace(0,end,33,dtype=int),end])
        quantiles=np.quantile(reference*np.exp(logp[:,select]),[.1,.5,.9],axis=0)
        scenario=[{'hours':round(float(grid[j]),4),'p10':round(float(quantiles[0,k]),4),'p50':round(float(quantiles[1,k]),4),'p90':round(float(quantiles[2,k]),4)} for k,j in enumerate(select)]
        rows=[]
        for i,threshold in enumerate(thresholds):
            hits=first[i]<=end
            finish=logp[:,end]>=threshold if threshold>=0 else logp[:,end]<=threshold
            extrema=maximum[:,end] if threshold>=0 else minimum[:,end]
            sensitivity=[float(np.mean(extrema*scale>=threshold if threshold>=0 else extrema*scale<=threshold)) for scale in scales]
            p=float(np.mean(hits)); low,high=np.quantile(sensitivity,[.1,.9])
            before=[]
            for j,stop in enumerate(thresholds):
                if threshold*stop >= 0:
                    before.append(None)
                else:
                    before.append(round(float(np.mean(hits & (first[i]<first[j]))),6))
            hit_times=grid[first[i,hits].astype(int)]
            rows.append({'touch':round(p,6),'finish':round(float(np.mean(finish)),6),'range':[round(min(float(low),p),6),round(max(float(high),p),6)],'medianHitHours':round(float(np.median(hit_times)),3) if len(hit_times) else None,'targetBeforeStop':before})
        horizons.append({'id':wid,'label':label,'calendarHours':calendar,'tradingHours':round(hours_i,4),'experimental':calendar<24,'scenario':scenario,'results':rows})
    del logp, maximum, minimum
    now=datetime.now(timezone.utc).isoformat()
    key=json.dumps({'asOf':timestamps[-1],'reference':reference,'sigma':sigma,'paths':paths,'seed':seed,'mode':mode},sort_keys=True)
    return {'schemaVersion':1,'id':hashlib.sha256(key.encode()).hexdigest()[:16],'mode':mode,'generatedAt':now,'asOf':timestamps[-1],
      'referencePrice':reference,'lastPrice':float(prices[-1]),'instrument':{'symbol':'CL=F','name':'WTI front-month futures','proxyFor':'TVC:USOIL'},
      'model':{'name':'GJR-GARCH / realized-volatility blend','calibrated':False,'paths':paths,'annualVolatility':round(sigma*np.sqrt(ANNUAL_HOURS),5),'parameters':fitted,'rangeMethod':'10–90 percentile volatility-bootstrap sensitivity; not a calibrated confidence interval','limitations':['CL=F is a futures proxy, not the TVC:USOIL feed.','Log-price model rejects zero and negative prices.','Hourly observations include overnight/roll gaps; rolling futures need adjustment before production validation.','Student-t endpoints use an approximate Gaussian bridge. Same-bin barrier ties count as stop-first.','CME weekday/DST calendar approximation excludes holidays and early closes.','Three-month windows use 90 calendar days; one-month uses 30.','No fitted news, geopolitical, OVX, regime or fundamental adjustments are active.']},
      'status':{'mode':'stable','reason':'Synthetic demonstration snapshot; no live market claims.' if mode=='demo' else 'Scheduled model snapshot; probabilities remain uncalibrated.'},
      'market':{'nasdaq':nasdaq,'brentSpread':brent_spread},'history':[{'time':t,'price':round(float(p),4),'nasdaq':None} for t,p in zip(timestamps[-120:],prices[-120:])],
      'levels':levels.tolist(),'horizons':horizons,'calibration':{'status':'not-validated','sampleSize':0,'brierScore':None,'reliability':[]},'events':[],'chokepoints':[],'drivers':[]}
