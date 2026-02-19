"""
Role: FULL_COLLECTION 모드로 대상 스크립트를 래핑 실행
Input: 없음(환경변수 FULL_COLLECTION=1 설정 후 하위 스크립트 실행)
Output: 하위 스크립트의 종료코드 반환
Side effect: 환경변수 설정, 하위 스크립트 실행
Author: 조비스
Updated: 2026-02-18
"""
import os
import subprocess
import sys

os.environ['FULL_COLLECTION'] = '1'
ret = subprocess.call([sys.executable, 'invest/scripts/fetch_supply.py'])
sys.exit(ret)
