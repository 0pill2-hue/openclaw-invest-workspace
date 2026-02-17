import os
import subprocess
import sys

os.environ['FULL_COLLECTION'] = '1'
ret = subprocess.call([sys.executable, 'invest/scripts/fetch_ohlcv.py'])
sys.exit(ret)
