import os
import subprocess
import sys

# full bootstrap scan instead of incremental-only
os.environ['TELEGRAM_INCREMENTAL_ONLY'] = '0'
ret = subprocess.call([sys.executable, 'invest/scripts/scrape_telegram_highspeed.py'])
sys.exit(ret)
