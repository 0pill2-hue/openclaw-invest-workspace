from pytrends.request import TrendReq
import pandas as pd
import os
import time
from datetime import datetime, timedelta

def fetch_google_trends(keywords):
    pytrends = TrendReq(hl='ko-KR', tz=540)
    
    output_dir = 'invest/data/alternative/trends'
    os.makedirs(output_dir, exist_ok=True)
    
    # 10 years ago to today
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*10)
    timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    
    for kw in keywords:
        print(f"Fetching Google Trends for: {kw} over {timeframe}")
        try:
            pytrends.build_payload([kw], cat=0, timeframe=timeframe, geo='KR')
            df = pytrends.interest_over_time()
            if not df.empty:
                df.to_csv(f"{output_dir}/{kw}_trends_10y.csv")
                print(f"Success: {kw}")
            else:
                print(f"No data for: {kw}")
        except Exception as e:
            print(f"Error fetching {kw}: {e}")
        time.sleep(5) # Throttling

if __name__ == "__main__":
    # Example consumer trends based on current research
    fetch_google_trends(['삼성전자', 'SK하이닉스', '로봇', '전기차', '태양광', '희토류', '제이에스링크', '드론'])
