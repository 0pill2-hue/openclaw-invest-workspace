import subprocess
import sys

COLLECTION_SCRIPTS = [
    'invest/scripts/full_fetch_ohlcv.py',
    'invest/scripts/full_fetch_supply.py',
    'invest/scripts/full_fetch_dart_disclosures.py',
    'invest/scripts/full_fetch_us_ohlcv.py',
    'invest/scripts/fetch_news_rss.py',
    'invest/scripts/fetch_macro_fred.py',
    'invest/scripts/fetch_trends.py',
    'invest/scripts/scrape_all_posts_v2.py',
    'invest/scripts/full_scrape_telegram.py',
]

POSTPROCESS_SCRIPTS = [
    # raw text -> image map / OCR
    'invest/scripts/image_harvester.py',
    # DART raw -> tagged
    'invest/scripts/dart_nlp_tagger.py',
]

for s in COLLECTION_SCRIPTS:
    print(f'== RUN {s} ==', flush=True)
    rc = subprocess.call([sys.executable, s])
    print(f'EXIT {rc}: {s}', flush=True)
    if rc != 0:
        sys.exit(rc)

print('== COLLECTION DONE. START POSTPROCESS ==', flush=True)

for s in POSTPROCESS_SCRIPTS:
    print(f'== RUN {s} ==', flush=True)
    rc = subprocess.call([sys.executable, s])
    print(f'EXIT {rc}: {s}', flush=True)
    if rc != 0:
        sys.exit(rc)

print('FULL COLLECTION + POSTPROCESS DONE', flush=True)
