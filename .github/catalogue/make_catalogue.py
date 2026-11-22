#!/usr/bin/env python3
"""
Rebuilds Spoken's free library list from LibriVox.

    python3 make_catalogue.py --out DIR --site DIR2

It asks LibriVox for every finished recording, asks the Internet Archive how often each has
been downloaded (used for "Most popular"), keeps the English ones and sorts them onto shelves.
DIR gets the list files; DIR2 gets catalogue.zip and version.json, which the app reads.
No key or account is needed.
"""
import hashlib, json, os, re, subprocess, sys, datetime, collections, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
OUT = os.path.join(HERE, 'list')
CHUNK = 400          # must match Catalogue.CHUNK in the app
DESC_MAX = 900
INCLUDE_ADULT = '--include-adult' in sys.argv


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


if arg('--out'):
    OUT = arg('--out')
SITE = arg('--site')

SHELVES = [
    ('Fiction', ['General Fiction', 'Literary Fiction', 'Published 1900 onward', 'Published 1800 -1900',
                 'Published before 1800', 'Family Life', 'Culture & Heritage Fiction', 'Epistolary Fiction',
                 'Fictional Biographies & Memoirs', 'Christian Fiction', 'Religious Fiction', 'Travel Fiction',
                 'Nature & Animal Fiction', 'Sports Fiction']),
    ('Mystery & Crime', ['Detective Fiction', 'Crime & Mystery Fiction',
                         'Suspense, Espionage, Political & Thrillers', 'True Crime']),
    ('Science Fiction & Fantasy', ['Science Fiction', 'Fantastic Fiction', 'Fantasy Fiction']),
    ('Adventure & Westerns', ['Action & Adventure Fiction', 'Action & Adventure', 'Westerns',
                              'Nautical & Marine Fiction', 'War & Military Fiction', 'Exploration']),
    ('Romance', ['Romance']),
    ('Historical Fiction', ['Historical Fiction', 'Historical']),
    ('Horror & Gothic', ['Horror & Supernatural Fiction', 'Gothic Fiction']),
    ('Humour & Satire', ['Humorous Fiction', 'Satire', 'Humor', 'Comedy']),
    ("Children's", ["Children's Fiction", "Children's Non-fiction", 'School']),
    ('Myths & Fairy Tales', ['Myths, Legends & Fairy Tales', 'Epics', 'Sagas']),
    ('Short Stories', ['Short Stories', 'Anthologies', 'Single Author Collections', 'Short works',
                       'Literary Collections']),
    ('Poetry', ['Poetry', 'Multi-version (Weekly and Fortnightly poetry)', 'Single author', 'Sonnets',
                'Ballads', 'Elegies & Odes', 'Lyric', 'Free Verse', 'Narratives']),
    ('Plays & Drama', ['Plays', 'Dramatic Readings', 'Tragedy', 'Drama', 'Performing Arts']),
    ('History', ['History', 'War & Military', 'Antiquity', 'Ancient', 'Middle Ages/Middle History',
                 'Medieval', 'Early Modern', 'Modern (19th C)', 'Modern (20th C)', 'Modern']),
    ('Biography & Memoir', ['Biography & Autobiography', 'Memoirs', 'Biography', 'Letters',
                            'Christianity - Biographies']),
    ('Ancient Classics', ['Classics (Greek & Latin Antiquity)', 'Asian Antiquity']),
    ('Philosophy', ['Philosophy', 'Contemporary', 'Atheism & Agnosticism']),
    ('Religion & Bible', ['Religion', 'Christianity - Other', 'Christianity - Commentary', 'Other religions',
                          'Bibles', 'King James Version', 'American Standard Version',
                          "Young's Literal Translation", 'Douay-Rheims Version', 'World English Bible',
                          'Weymouth New Testament']),
    ('Science & Nature', ['Science', 'Nature', 'Animals & Nature', 'Animals', 'Life Sciences', 'Psychology',
                          'Astronomy, Physics & Mechanics', 'Chemistry', 'Earth Sciences', 'Mathematics',
                          'Medical', 'Technology & Engineering', 'Gardening']),
    ('Travel', ['Travel & Geography']),
    ('Society & Politics', ['Political Science', 'Social Science (Culture & Anthropology)', 'Law',
                            'Business & Economics', 'Education']),
    ('Essays & Ideas', ['Essays & Short Works', 'Essays', 'Literary Criticism', 'Periodicals & Magazines',
                        'Short non-fiction', '*Non-fiction', 'Reference', 'Writing & Linguistics',
                        'Language learning']),
    ('Home, Health & Hobbies', ['Self-Help', 'Cooking', 'House & Home', 'Crafts & Hobbies', 'Health & Fitness',
                                'Family & Relationships', 'Family', 'Sports & Recreation', 'Games',
                                'Transportation']),
    ('Arts & Music', ['Art, Design & Architecture', 'Music', 'Arts']),
]
ADULT = {'Erotica'}
RENAME = {'*Non-fiction': 'General Non-fiction', 'Humor': 'Humour', 'Single author': 'Single-poet Collections',
          'Multi-version (Weekly and Fortnightly poetry)': 'One Poem, Many Voices',
          'Published 1800 -1900': 'Published 1800 to 1900'}


def flat(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\t', ' ')).strip()


def clip(text):
    text = flat(text)
    if len(text) <= DESC_MAX:
        return text
    cut = text[:DESC_MAX]
    stop = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    if stop > DESC_MAX * 0.6:
        return cut[:stop + 1]
    return cut[:cut.rfind(' ')] + '…'


def author(names):
    full = [flat(' '.join(p for p in a if p)) for a in names]
    full = [n for n in full if n]
    if not full:
        return ''
    if len(full) > 3:
        return 'Various'
    return ', '.join(full)


def main():
    os.makedirs(CACHE, exist_ok=True)
    raw = os.path.join(CACHE, 'raw.jsonl')
    pop = os.path.join(CACHE, 'popularity.json')
    if '--keep' not in sys.argv or not os.path.exists(raw):
        if os.path.exists(raw):
            os.remove(raw)
        subprocess.check_call([sys.executable, os.path.join(HERE, 'fetch_librivox.py'), raw])
        subprocess.check_call([sys.executable, os.path.join(HERE, 'fetch_popularity.py'), pop])
    books = [json.loads(line) for line in open(raw, encoding='utf-8')]
    popularity = json.load(open(pop)) if os.path.exists(pop) else {}

    shelf_of = {}
    for shelf, genres in SHELVES:
        for g in genres:
            shelf_of[g] = shelf

    kept, skipped = [], collections.Counter()
    for b in books:
        if b['l'] != 'English':
            skipped['not English'] += 1; continue
        if b['ns'] <= 0:
            skipped['no chapters listed'] += 1; continue
        if not INCLUDE_ADULT and any(g in ADULT for g in b['g']):
            skipped['adult'] += 1; continue
        if not flat(b['t']):
            skipped['no title'] += 1; continue
        kept.append(b)
    kept.sort(key=lambda b: b['id'])

    counts = collections.Counter(g for b in kept for g in (b['g'] or ['Uncategorised']))
    order = [s for s, _ in SHELVES] + ['More']
    genre_rows = []
    for g, _ in counts.most_common():
        genre_rows.append((g, shelf_of.get(g, 'More')))
    genre_rows.sort(key=lambda r: (order.index(r[1]), -counts[r[0]]))
    index = {g: i for i, (g, _) in enumerate(genre_rows)}

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    with open(os.path.join(OUT, 'genres.tsv'), 'w', encoding='utf-8') as f:
        for i, (g, shelf) in enumerate(genre_rows):
            f.write(f'{i}\t{RENAME.get(g, g)}\t{shelf}\n')

    lines = []
    for b in kept:
        gs = ','.join(str(index[g]) for g in (b['g'] or ['Uncategorised']))
        year = b['y'] if str(b['y']).isdigit() else '0'
        lines.append('\t'.join([
            str(b['id']), flat(b['t']), author(b['a']), gs, str(b['s']), str(b['ns']), str(b['rc']),
            flat(b['r']) if b['rc'] == 1 else '', str(year), str(popularity.get(b['ia'].lower(), 0)),
        ]))
    # Plain text on purpose: the Android build unpacks any ".gz" file it finds in assets and renames it,
    # so the files are left uncompressed here and the app package compresses them itself.
    with open(os.path.join(OUT, 'books.tsv'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    for start in range(0, len(kept), CHUNK):
        part = kept[start:start + CHUNK]
        with open(os.path.join(OUT, f'd{start // CHUNK}.tsv'), 'w', encoding='utf-8') as f:
            f.write(''.join(f"{b['id']}\t{clip(b['d'])}\n" for b in part))
    today = datetime.date.today()
    with open(os.path.join(OUT, 'built.txt'), 'w') as f:
        f.write(today.strftime('%-d %B %Y') + '\n')
    # The app compares this date with its own to decide whether a list on the website is newer.
    with open(os.path.join(OUT, 'stamp.txt'), 'w') as f:
        f.write(today.isoformat() + '\n')

    if SITE:
        # The website's copy: one zip of the same files, and a small file saying how new it is.
        os.makedirs(SITE, exist_ok=True)
        zpath = os.path.join(SITE, 'catalogue.zip')
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name in sorted(os.listdir(OUT)):
                info = zipfile.ZipInfo(name, date_time=(today.year, today.month, today.day, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, open(os.path.join(OUT, name), 'rb').read(), compresslevel=9)
        data = open(zpath, 'rb').read()
        with open(os.path.join(SITE, 'version.json'), 'w') as f:
            json.dump({'stamp': today.isoformat(), 'built': today.strftime('%-d %B %Y'), 'books': len(kept),
                       'zip': 'catalogue.zip', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, f, indent=1)
            f.write('\n')
        print(f'website copy: {zpath} ({len(data) / 1e6:.1f} MB)')

    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    hours = sum(b['s'] for b in kept) / 3600
    shelf_counts = collections.Counter()
    for b in kept:
        for s in {shelf_of.get(g, 'More') for g in (b['g'] or ['Uncategorised'])}:
            shelf_counts[s] += 1
    print(f'{len(kept):,} English books, {hours:,.0f} hours, {len(genre_rows)} categories on {len(shelf_counts)} shelves')
    print(f'single reader: {sum(1 for b in kept if b["rc"] == 1):,}; with a popularity figure: {sum(1 for b in kept if popularity.get(b["ia"].lower())):,}')
    print('left out:', dict(skipped))
    print(f'written to assets/catalogue: {size / 1e6:.1f} MB before the app package compresses it')
    for s in order:
        if shelf_counts[s]:
            print(f'  {shelf_counts[s]:>6,}  {s}')


if __name__ == '__main__':
    main()
