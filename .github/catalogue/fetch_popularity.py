#!/usr/bin/env python3
"""Fetch download counts for the LibriVox collection on the Internet Archive (used as 'most popular')."""
import json, sys, urllib.request, urllib.parse, time
out = {}
cursor = None
while True:
    q = {'q': 'collection:librivoxaudio', 'fields': 'identifier,downloads', 'count': '10000'}
    if cursor: q['cursor'] = cursor
    url = 'https://archive.org/services/search/v1/scrape?' + urllib.parse.urlencode(q)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'SpokenCatalogueBuilder/1.0'}), timeout=120) as r:
                d = json.loads(r.read()); break
        except Exception as e:
            time.sleep(5 * (attempt + 1))
    else:
        raise SystemExit('failed')
    for it in d.get('items', []):
        out[it['identifier'].lower()] = int(it.get('downloads') or 0)
    cursor = d.get('cursor')
    print(len(out), flush=True)
    if not cursor: break
json.dump(out, open(sys.argv[1], 'w'))
print('DONE')
