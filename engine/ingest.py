"""Validated, archived market inputs. No credentials or provider code runs in the browser."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

UTC = timezone.utc


def utcnow():
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS bars (
      symbol TEXT NOT NULL, timestamp TEXT NOT NULL, close REAL NOT NULL,
      high REAL NOT NULL, low REAL NOT NULL, source TEXT NOT NULL,
      fetched_at TEXT NOT NULL, PRIMARY KEY(symbol,timestamp));
    CREATE TABLE IF NOT EXISTS pulls (
      id INTEGER PRIMARY KEY, fetched_at TEXT NOT NULL, domain TEXT NOT NULL,
      status TEXT NOT NULL, details TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
      published_at TEXT, fetched_at TEXT NOT NULL, source TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audits (
      id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, detail TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS snapshots (
      id TEXT PRIMARY KEY, published_at TEXT NOT NULL, payload TEXT NOT NULL);
    ''')
    return db


def fetch_bars(symbol, now=None):
    """Yahoo hourly bar timestamps mark bar starts; discard the unfinished bar."""
    import yfinance as yf
    now = now or datetime.now(UTC)
    frame = yf.Ticker(symbol).history(period='1mo', interval='1h',
                                    auto_adjust=False, actions=False, timeout=20,
                                    raise_errors=True)
    if frame.empty:
        raise ValueError(f'{symbol}: provider returned no history')
    rows = []
    for index, row in frame.iterrows():
        stamp = index.to_pydatetime()
        if stamp.tzinfo is None:
            raise ValueError(f'{symbol}: timezone missing')
        stamp = stamp.astimezone(UTC)
        # Only closed bars, no short bar mixed into an hourly volatility estimate.
        if (now - stamp).total_seconds() < 3600:
            continue
        close, high, low = (float(row[k]) for k in ('Close', 'High', 'Low'))
        if not all(math.isfinite(v) and v > 0 for v in (close, high, low)):
            raise ValueError(f'{symbol}: nonpositive/nonfinite bar; log model cannot use this series')
        if not low <= close <= high:
            raise ValueError(f'{symbol}: inconsistent OHLC')
        rows.append({'timestamp': (stamp + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'),
                     'close': close, 'high': high, 'low': low})
    rows.sort(key=lambda r: r['timestamp'])
    if not rows:
        raise ValueError(f'{symbol}: no complete bars')
    if len({r['timestamp'] for r in rows}) != len(rows):
        raise ValueError(f'{symbol}: duplicate timestamps')
    return rows


def archive_bars(db, symbol, rows):
    stamp = utcnow()
    with db:
        db.executemany('INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?)',
                       [(symbol, r['timestamp'], r['close'], r['high'], r['low'],
                         'Yahoo Finance via yfinance', stamp) for r in rows])
        db.execute('INSERT INTO pulls(fetched_at,domain,status,details) VALUES(?,?,?,?)',
                   (stamp, symbol, 'ok', json.dumps({'bars':len(rows),'last':rows[-1]['timestamp']})))


def archived_bars(db, symbol, limit=800):
    rows = db.execute('SELECT timestamp,close,high,low FROM bars WHERE symbol=? '
                      'ORDER BY timestamp DESC LIMIT ?', (symbol, limit)).fetchall()
    return [dict(zip(('timestamp','close','high','low'), r)) for r in reversed(rows)]


def log_failure(db, domain, error):
    with db:
        db.execute('INSERT INTO pulls(fetched_at,domain,status,details) VALUES(?,?,?,?)',
                   (utcnow(), domain, 'error', str(error)[:300]))


def collect_market(db, now=None):
    """Archive failures; only fresh WTI bars can replace a published model."""
    now = now or datetime.now(UTC)
    result = {}
    for symbol in ('CL=F', 'BZ=F', '^IXIC', '^OVX'):
        try:
            bars = fetch_bars(symbol, now)
            archive_bars(db, symbol, bars)
            result[symbol] = archived_bars(db, symbol)
        except Exception as exc:
            log_failure(db, symbol, exc)
            if symbol == 'CL=F':
                raise RuntimeError('WTI provider unavailable; existing snapshot retained') from exc
            result[symbol] = []
    wti = result['CL=F']
    age = (now - datetime.fromisoformat(wti[-1]['timestamp'].replace('Z','+00:00'))).total_seconds()
    if len(wti) < 100 or age > 4*3600 or age < 0:
        raise ValueError('WTI requires at least 100 complete hourly bars and a last bar under four hours old. '
                         'Weekend/holiday closes retain the last snapshot.')
    return result


def collect_eia_headlines(db):
    """Official headline/link metadata only, context-only and never a model signal."""
    feed_url = 'https://www.eia.gov/rss/todayinenergy.xml'
    req = urllib.request.Request(feed_url, headers={'User-Agent':'WTIObservatory/1.0 (RSS reader)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError('RSS exceeds size limit')
        root = ET.fromstring(payload)
        items = []
        for item in root.findall('./channel/item')[:30]:
            title = (item.findtext('title') or '').strip()[:300]
            url = (item.findtext('link') or '').strip()
            host = (urlparse(url).hostname or '').lower()
            if not title or urlparse(url).scheme != 'https' or not (host == 'eia.gov' or host.endswith('.eia.gov')):
                continue
            date = item.findtext('pubDate')
            try:
                published = parsedate_to_datetime(date).astimezone(UTC).isoformat() if date else None
            except (TypeError, ValueError):
                published = None
            ident = hashlib.sha256(url.encode()).hexdigest()
            record = {'id':ident, 'title':title, 'url':url, 'publishedAt':published,
                      'source':'EIA Today in Energy', 'tier':1, 'modelContribution':0,
                      'contextOnly':True}
            items.append(record)
            with db:
                db.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?)',
                           (ident,title,url,published,utcnow(),'EIA Today in Energy'))
        return items[:8]
    except Exception as exc:
        log_failure(db, 'EIA RSS', exc)
        return []
