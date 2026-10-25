"""CLI: python -m engine.update. Failed inputs never overwrite the last snapshot."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from engine.ingest import connect, collect_market, collect_eia_headlines, log_failure, utcnow
from engine.snapshot import build_snapshot
from engine.stability import publish


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def update(output='public/data/snapshot.json', database='state/archive.sqlite', paths=12000):
    destination = Path(output)
    previous = json.loads(destination.read_text()) if destination.exists() else None
    db = connect(database)
    try:
        market = collect_market(db)
        wti = market['CL=F']
        stamp = wti[-1]['timestamp']
        # A repeated provider response is not new evidence and must not advance persistence counters.
        prior_asof = db.execute("SELECT value FROM state WHERE key='last_processed_bar'").fetchone()
        if prior_asof and json.loads(prior_asof[0]) == stamp:
            print('No new complete WTI bar; retained the published snapshot.')
            return False
        nasdaq_rows = market['^IXIC']
        nasdaq = None
        if len(nasdaq_rows) >= 2:
            nasdaq = {'price':nasdaq_rows[-1]['close'],
                      'changePct':100*(nasdaq_rows[-1]['close']/nasdaq_rows[-2]['close']-1),
                      'asOf':nasdaq_rows[-1]['timestamp'], 'changePeriod':'previous hourly bar'}
        brent = market['BZ=F']
        # Compare matched timestamps, not two unrelated last traded prices.
        brent_at_wti = next((r for r in reversed(brent) if r['timestamp'] == stamp), None)
        spread = brent_at_wti['close'] - wti[-1]['close'] if brent_at_wti else None
        live_previous = previous if previous and previous.get('mode') == 'live' else None
        candidate = build_snapshot([r['close'] for r in wti], [r['timestamp'] for r in wti],
                                   mode='live', paths=paths, nasdaq=nasdaq,
                                   brent_spread=spread, previous=live_previous)
        nasdaq_by_time = {r['timestamp']: r['close'] for r in nasdaq_rows}
        for point in candidate.get('history', []):
            point['nasdaq'] = nasdaq_by_time.get(point['time'])
        candidate['headlines'] = collect_eia_headlines(db)
        candidate['dataSources'] = [
            {'symbol':symbol, 'source':'Yahoo Finance via yfinance',
             'asOf':rows[-1]['timestamp'] if rows else None,
             'status':'available' if rows else 'unavailable',
             'usage':'model' if symbol == 'CL=F' else 'context only'}
            for symbol, rows in market.items()]
        candidate['instrumentNote'] = 'Model uses Yahoo CL=F front-month WTI futures, not TradingView TVC:USOIL. Quotes and contract rolls can differ.'
        row = db.execute("SELECT value FROM state WHERE key='publish'").fetchone()
        state = json.loads(row[0]) if row else {}
        # Demo is a fixture, never the predecessor of a live publication.
        live_previous = previous if previous and previous.get('mode') == 'live' else None
        published, state, audits = publish(candidate, live_previous, state, major_event=False)
        serialized = json.dumps(published, separators=(',', ':'), allow_nan=False)
        # Roll back publication state if writing the static snapshot fails.
        # A failed database commit after file replacement can safely reprocess the bar.
        with db:
            db.execute('INSERT OR REPLACE INTO state VALUES(?,?)', ('publish', json.dumps(state)))
            db.execute('INSERT OR REPLACE INTO state VALUES(?,?)', ('last_processed_bar', json.dumps(stamp)))
            for audit in audits:
                db.execute('INSERT INTO audits(timestamp,detail) VALUES(?,?)', (utcnow(),json.dumps(audit)))
            ident = str(published.get('id', published.get('generatedAt', utcnow())))
            db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?)', (ident,utcnow(),serialized))
            atomic_json(destination, published)
        print(f'Published snapshot from {stamp}; input and audit archive saved.')
        return True
    except Exception as exc:
        log_failure(db, 'update', exc)
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='public/data/snapshot.json')
    parser.add_argument('--database', default='state/archive.sqlite')
    parser.add_argument('--paths', type=int, default=12000)
    args = parser.parse_args()
    if not 1000 <= args.paths <= 100000:
        parser.error('--paths must be between 1000 and 100000')
    update(args.output, args.database, args.paths)


if __name__ == '__main__':
    main()
