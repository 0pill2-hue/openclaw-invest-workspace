import FinanceDataReader as fdr
import pandas as pd
import os

def fetch_kr_stock_list():
    """
    Role: fetch_kr_stock_list 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    print("Fetching KRX stock list...")
    # KRX is the combined list of KOSPI, KOSDAQ, KONEX
    df_krx = fdr.StockListing('KRX')
    
    output_path = 'invest/data/master/kr_stock_list.csv'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_krx.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Saved {len(df_krx)} stocks to {output_path}")

if __name__ == "__main__":
    fetch_kr_stock_list()
