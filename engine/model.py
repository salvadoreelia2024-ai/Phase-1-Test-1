"""Small, inspectable research model. No claim of calibrated forecasting skill."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import ndtr

ANNUAL_HOURS = 252 * 23


def trading_hours(start, calendar_hours):
    """CME weekday session approximation; US DST aware; excludes 17–18 ET.

    Does not include exchange holidays / shortened sessions. Integrates in
    15-minute pieces so horizons need not start exactly on an hour.
    """
    if isinstance(start, str):
        start = datetime.fromisoformat(start.replace('Z', '+00:00'))
    if start.tzinfo is None:
        raise ValueError('Start must be timezone aware')
    end = start + timedelta(hours=calendar_hours)
    current, total = start, 0.0
    while current < end:
        nxt = min(end, current + timedelta(minutes=15))
        local = (current + (nxt-current)/2).astimezone(ZoneInfo('America/New_York'))
        day, hour = local.weekday(), local.hour + local.minute/60
        opened = (day < 4 and not 17 <= hour < 18) or (day == 4 and hour < 17) or (day == 6 and hour >= 18)
        if opened:
            total += (nxt-current).total_seconds()/3600
        current = nxt
    return total


def fit_volatility(prices):
    prices = np.asarray(prices, dtype=float)
    if len(prices) < 100 or not np.all(np.isfinite(prices)) or np.any(prices <= 0):
        raise ValueError('Need at least 100 finite, positive hourly closes; negative WTI needs a separate model')
    r = np.diff(np.log(prices)) * 100
    base = max(float(np.var(r)), 1e-6)
    def filter_variance(theta):
        omega, alpha, gamma, beta = theta
        variance = np.empty(len(r)); variance[0] = base
        for i in range(1, len(r)):
            variance[i] = omega + (alpha + gamma*(r[i-1] < 0))*r[i-1]**2 + beta*variance[i-1]
        return np.maximum(variance, 1e-10)
    def loss(theta):
        if theta[1] + theta[2]/2 + theta[3] >= .999:
            return 1e12
        v = filter_variance(theta)
        return float(np.mean(np.log(v) + r*r/v))
    fit = minimize(loss, [base*.04, .04, .04, .90], method='SLSQP',
                   bounds=[(1e-8, base*2), (0,.4), (0,.4), (0,.99)],
                   constraints=[{'type':'ineq','fun':lambda t: .998-t[1]-t[2]/2-t[3]}],
                   options={'maxiter':90,'ftol':1e-7})
    theta = fit.x if fit.success else np.array([base*.04,.04,.04,.90])
    v = filter_variance(theta)
    next_variance = theta[0] + (theta[1] + theta[2]*(r[-1]<0))*r[-1]**2 + theta[3]*v[-1]
    garch = math.sqrt(next_variance)/100
    realized = float(np.std(r[-min(120,len(r)):], ddof=1))/100
    sigma = float(np.clip(.6*garch + .4*realized, .0001, .10))
    return sigma, {'omega':float(theta[0])/10000,'alpha':float(theta[1]),'gamma':float(theta[2]),'beta':float(theta[3]),'fitConverged':bool(fit.success)}


def time_grid(horizons):
    """Fine short-window grid; longer windows have <=3 trading-hour steps."""
    end = max(horizons)
    grid = set([0.0, *horizons])
    x = 0.0
    while x < end:
        x = min(end, x + (.25 if x < 24 else 1 if x < 168 else 3))
        grid.add(x)
    return np.array(sorted(grid))


def simulate(reference, sigma, grid, paths=12000, seed=1729, gaussian=False):
    """Student-t endpoints with a conditional Gaussian bridge approximation.

    Bridge extrema marginals are exact only in Gaussian mode. Upper/lower
    bridge extrema are sampled independently; joint barrier order is therefore
    reported conservatively when both first cross within the same grid cell.
    """
    grid = np.asarray(grid,dtype=float)
    if not math.isfinite(reference) or reference <= 0 or not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("Reference and volatility must be positive and finite")
    if grid.ndim != 1 or not len(grid) or grid[0] != 0 or np.any(np.diff(grid)<=0) or not np.all(np.isfinite(grid)):
        raise ValueError("Grid must start at zero and strictly increase")
    if paths < 1:
        raise ValueError("Paths must be positive")
    rng = np.random.default_rng(seed)
    dt = np.diff(grid)
    z = rng.normal(size=(paths,len(dt))) if gaussian else rng.standard_t(7,size=(paths,len(dt)))*math.sqrt(5/7)
    steps = sigma*np.sqrt(dt)[None,:]*z
    # Drift-neutral log process provides a clean reflection-principle baseline.
    logp = np.c_[np.zeros(paths), np.cumsum(steps,axis=1)]
    a,b = logp[:,:-1], logp[:,1:]
    variance = sigma*sigma*dt[None,:]
    up = (a+b+np.sqrt((a-b)**2-2*variance*np.log(np.maximum(rng.random(a.shape),1e-15))))/2
    down = (a+b-np.sqrt((a-b)**2-2*variance*np.log(np.maximum(rng.random(a.shape),1e-15))))/2
    return logp, np.maximum.accumulate(np.c_[np.zeros(paths),up],axis=1), np.minimum.accumulate(np.c_[np.zeros(paths),down],axis=1)


def reflection_touch(reference, target, sigma, hours):
    if target == reference:
        return 1.0
    if hours <= 0:
        return 0.0
    return float(2*ndtr(-abs(math.log(target/reference))/(sigma*math.sqrt(hours))))
