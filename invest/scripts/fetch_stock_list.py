import FinanceDataReader as fdr
import pandas as pd
import os

def fetch_kr_stock_list():
    print("Fetching KRX stock list...")
    # KRX is the combined list of KOSPI, KOSDAQ, KONEX
    df_krx = fdr.StockListing('KRX')
    
    output_path = 'invest/data/master/kr_stock_list.csv'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_krx.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Saved {len(df_krx)} stocks to {output_path}")

if __name__ == "__main__":
    fetch_kr_stock_list()
