import os
import subprocess
import sys

os.environ['FULL_COLLECTION'] = '1'
os.environ.setdefault('US_OHLCV_BASE_START_DATE', '2016-01-01')
ret = subprocess.call([sys.executable, 'invest/scripts/fetch_us_ohlcv.py'])
sys.exit(ret)
