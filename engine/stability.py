"""Atomic snapshot gating keeps charts, barriers and displayed odds coherent."""
from copy import deepcopy


def publish(candidate, previous, state=None, major_event=False, deadband=.02, persistence=2):
    """Return (published snapshot, next state, JSON-safe audit records).

    Gate the entire snapshot, not individual cells. Per-cell rate caps are
    deliberately deferred: they can break ordering and probability identities.
    Caller persists state even when the prior snapshot is retained.
    """
    state=deepcopy(state or {})
    if previous is None or previous.get('mode') != candidate['mode']:
        return candidate,{'pending':0},[{'time':candidate['generatedAt'],'oldId':previous.get('id') if previous else None,'newId':candidate['id'],'cause':'Initial snapshot'}]
    if candidate['id'] == previous['id']:
        return previous,{'pending':0},[]
    # Compare common absolute price levels, not shifted relative indexes.
    lookup={value:i for i,value in enumerate(previous['levels'])}
    deltas=[]
    changes={}
    audit_values=[]
    for horizon_index,(oldh,newh) in enumerate(zip(previous['horizons'],candidate['horizons'])):
        for i,level in enumerate(candidate['levels']):
            if level in lookup:
                old_value=oldh['results'][lookup[level]]['touch']
                new_value=newh['results'][i]['touch']
                delta=new_value-old_value
                deltas.append(abs(delta))
                changes[f'{horizon_index}|{level}']=delta
                if abs(delta)>=.000001:
                    audit_values.append({'horizon':newh.get('id',horizon_index),'target':level,'old':old_value,'new':new_value})
    maximum=max(deltas,default=1.0)
    prior_changes=state.get('candidateChanges',{})
    dot=sum(value*prior_changes.get(key,0) for key,value in changes.items())
    norm=(sum(v*v for v in changes.values())*sum(v*v for v in prior_changes.values()))**.5
    consistent=norm>0 and dot/norm>.5
    state['pending']=(int(state.get('pending',0))+1 if consistent else 1) if maximum>deadband else 0
    state['candidateChanges']=changes if maximum>deadband else {}
    if major_event or state['pending']>=persistence:
        candidate=deepcopy(candidate)
        cause=candidate['status']['reason'] if major_event else f'Model update persisted for {persistence} runs; maximum target-grid change {maximum*100:.0f} points.'
        candidate['status']['reason']=cause
        if major_event:
            candidate['status']['mode']='shock'
        audit={'time':candidate['generatedAt'],'oldId':previous['id'],'newId':candidate['id'],'cause':cause,'maximumChange':maximum,'changes':audit_values}
        return candidate,{'pending':0},[audit]
    return previous,state,[]
