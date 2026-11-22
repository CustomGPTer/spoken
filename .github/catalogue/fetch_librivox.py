#!/usr/bin/env python3
"""Fetch the full LibriVox catalogue (all languages) into condensed JSON lines."""
import json, sys, time, urllib.request, urllib.error, html, re, os
out_path = sys.argv[1]
LIMIT = 100
TAG = re.compile(r'<[^>]+>')
def clean(s):
    if not s: return ''
    s = html.unescape(TAG.sub(' ', s))
    return re.sub(r'\s+', ' ', s).strip()
def get(offset):
    url = ('https://librivox.org/api/feed/audiobooks?format=json&extended=1&coverart=1'
           f'&limit={LIMIT}&offset={offset}')
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'SpokenCatalogueBuilder/1.0'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code == 404: return {'books': []}
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f'failed at offset {offset}')
done = 0
start = 0
if os.path.exists(out_path):
    with open(out_path) as f:
        for line in f: done += 1
    start = (done // LIMIT) * LIMIT
    # truncate to whole pages
    lines = open(out_path).read().splitlines()[:start]
    open(out_path, 'w').write('\n'.join(lines) + ('\n' if lines else ''))
empty = 0
with open(out_path, 'a') as out:
    offset = start
    while True:
        d = get(offset)
        books = d.get('books') or []
        if isinstance(books, dict): books = list(books.values())
        if not books:
            empty += 1
            if empty >= 2: break
            offset += LIMIT
            continue
        empty = 0
        for b in books:
            secs = b.get('sections') or []
            readers = {}
            for s in secs:
                for r in (s.get('readers') or []):
                    n = (r.get('display_name') or '').strip()
                    if n: readers[n] = readers.get(n, 0) + 1
            top = sorted(readers.items(), key=lambda kv: -kv[1])
            ia = (b.get('url_iarchive') or '').rstrip('/').split('/')[-1]
            rec = {
                'id': int(b['id']), 't': clean(b.get('title')), 'd': clean(b.get('description')),
                'l': b.get('language') or '', 'y': b.get('copyright_year') or '',
                'n': int(b.get('num_sections') or 0), 's': int(b.get('totaltimesecs') or 0),
                'a': [[clean(a.get('first_name')), clean(a.get('last_name'))] for a in (b.get('authors') or [])],
                'g': [clean(g.get('name')) for g in (b.get('genres') or [])],
                'rc': len(readers), 'r': top[0][0] if top else '',
                'ia': ia, 'c': b.get('coverart_jpg') or '', 'ns': len(secs),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + '\n')
        out.flush()
        offset += LIMIT
        print(offset, flush=True)
        time.sleep(0.4)
print('DONE', flush=True)
