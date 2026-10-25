"""Evaluation utilities. Training a map is not evidence of test performance."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


def metrics(probabilities, outcomes, bins=10):
    p,y=np.asarray(probabilities,dtype=float),np.asarray(outcomes,dtype=float)
    if p.ndim!=1 or len(p)==0 or p.shape!=y.shape or not np.all(np.isfinite(p)) or np.any((p<0)|(p>1)) or not np.all(np.isin(y,[0,1])):
        raise ValueError('Require equal nonempty probability and binary-outcome vectors')
    clipped=np.clip(p,1e-12,1-1e-12)
    reliability=[]
    assignments=np.minimum((p*bins).astype(int),bins-1)
    for i in range(bins):
        mask=assignments==i
        if np.any(mask):
            reliability.append({'predicted':float(p[mask].mean()),'observed':float(y[mask].mean()),'count':int(mask.sum())})
    return {'sampleSize':len(p),'brierScore':float(np.mean((p-y)**2)),'logLoss':float(-np.mean(y*np.log(clipped)+(1-y)*np.log(1-clipped))),'reliability':reliability}


def fit_platt(probabilities, outcomes):
    """Fit only to already out-of-sample predictions; evaluate on later data."""
    metrics(probabilities,outcomes)
    if len(probabilities)<100 or len(set(outcomes))<2:
        raise ValueError('Calibration needs >=100 predictions and both outcomes')
    p=np.clip(probabilities,1e-6,1-1e-6); x=np.log(p/(1-p)); y=np.asarray(outcomes)
    def loss(ab):
        z=ab[0]*x+ab[1]
        return float(np.mean(np.logaddexp(0,z)-y*z)+.001*((ab[0]-1)**2+ab[1]**2))
    fit=minimize(loss,[1.,0.],bounds=[(.1,5.),(-3.,3.)])
    if not fit.success:
        raise ValueError('Calibration fit did not converge')
    return {'slope':float(fit.x[0]),'intercept':float(fit.x[1]),'trainingCount':len(p)}


def apply_platt(probabilities, fitted):
    p=np.asarray(probabilities,dtype=float)
    clipped=np.clip(p,1e-6,1-1e-6)
    result=expit(fitted['slope']*np.log(clipped/(1-clipped))+fitted['intercept'])
    return np.where(p==0,0,np.where(p==1,1,result))


def walk_forward_splits(count, train_size=1000, test_size=100, embargo=24):
    """Expanding train; embargo excludes overlapping forward-label periods.

    Set embargo >= maximum label horizon in observation units. This splitter
    does not download historical data or claim the architecture's regime gates.
    """
    if min(count,train_size,test_size)<1 or embargo<0:
        raise ValueError('Invalid split sizes')
    start=train_size+embargo
    while start+test_size<=count:
        yield np.arange(0,start-embargo),np.arange(start,start+test_size)
        start+=test_size
