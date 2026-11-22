#!/usr/bin/env python3
"""Checks a newly built list before it replaces the one on the website.

    python3 check.py <folder with the new catalogue.zip and version.json> <the site's catalogue folder>

The new list is refused if it is damaged or much shorter than the one it would replace.
"""
import hashlib, json, os, shutil, sys, zipfile

new, live = sys.argv[1], sys.argv[2]
info = json.load(open(os.path.join(new, 'version.json')))
data = open(os.path.join(new, 'catalogue.zip'), 'rb').read()
assert hashlib.sha256(data).hexdigest() == info['sha256'], 'the zip does not match its checksum'
assert len(data) == info['bytes'], 'the zip is not the stated size'
names = set(zipfile.ZipFile(os.path.join(new, 'catalogue.zip')).namelist())
for need in ('books.tsv', 'genres.tsv', 'built.txt', 'stamp.txt', 'd0.tsv'):
    assert need in names, need + ' is missing'
old = 0
try:
    old = json.load(open(os.path.join(live, 'version.json')))['books']
except Exception:
    pass
floor = max(15000, int(old * 0.97))
assert info['books'] >= floor, f"only {info['books']} books, expected at least {floor}"
os.makedirs(live, exist_ok=True)
for f in ('catalogue.zip', 'version.json'):
    shutil.copy(os.path.join(new, f), os.path.join(live, f))
print(f"{info['books']} books (was {old}), dated {info['stamp']}")
