# proxy_provider.py
import akshare as ak
import pandas as pd
import time
import random
import streamlit as st

class ProxyDataFetcher:
    def __init__(self):
        self.ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) Safari/604.1"
        ]

    def _sleep_protection(self):
        """物理防护：模拟人类随机停顿"""
        time.sleep(random.uniform(0.5, 1.5))

    def safe_get_stock_hist(self, symbol, start, end):
        """带冗余备份的历史行情获取"""
        self._sleep_protection()
        
        # 路径 A: 东方财富
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
            if df is not None and not df.empty:
                df['日期'] = pd.to_datetime(df['日期'])
                return df[['日期', '收盘']]
        except:
            pass

        # 路径 B: 新浪源 (Sina)
        try:
            df = ak.stock_zh_a_daily(symbol=f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}", 
                                    start_date=start, end_date=end)
            if df is not None and not df.empty:
                df = df.rename(columns={'close': '收盘'})
                df['日期'] = pd.to_datetime(df.index)
                return df[['日期', '收盘']]
        except:
            return None

    def safe_get_etf_snapshot(self, assets_dict):
        """带容错的 ETF 实时监测"""
        results = []
        try:
            # 路径：新浪分类快照（目前对被封 IP 最友好的接口）
            snapshot = ak.fund_etf_category_sina(symbol="ETF基金")
            for code, name in assets_dict.items():
                full_code = f"sh{code}" if code.startswith('5') else f"sz{code}"
                match = snapshot[snapshot['代码'] == full_code]
                if not match.empty:
                    curr = float(match['最新价'].iloc[0])
                    change = float(match['涨跌额'].iloc[0])
                    roc = (change / (curr - change)) * 100 if curr != change else 0
                    results.append({"name": name, "curr": curr, "roc": roc})
                self._sleep_protection()
            return results
        except:
            return []

# 实例化
fetcher = ProxyDataFetcher()