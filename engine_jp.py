# engine_jp.py
import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import calendar
import os # ファイル存在確認用

# ==========================================
#              核心ツール関数ライブラリ
# ==========================================

@st.cache_data(ttl=3600) # キャッシュを追加し、リクエストの重複を避ける
def get_stock_data(symbol, start_date, end_date):
    """日次データを取得（yfinance版）"""
    try:
        # yfinanceを使用してデータを取得
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if df.empty: return None
        
        # MultiIndex対策：カラムを平坦化
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        # カラム名を統一（日付, 終値）
        df.rename(columns={'Date': '日付', 'Close': '終値'}, inplace=True)
        df['日付'] = pd.to_datetime(df['日付'])
        return df[['日付', '終値']]
    except Exception as e:
        return None

def get_nearest_price_info(target_date, df):
    """
    最近の取引日情報を検索
    戻り値: (実際の取引日, 終値, 差異日数の説明)
    """
    if df is None or df.empty:
        return None, None, ""
        
    # 時間差の絶対値が最小のインデックスを特定
    nearest_idx = (df['日付'] - target_date).abs().idxmin()
    actual_date = df.loc[nearest_idx, '日付']
    price = df.loc[nearest_idx, '終値']
    
    diff_days = (actual_date - target_date).days
    
    note = "当日"
    if diff_days > 0: note = f"{diff_days}日後"
    elif diff_days < 0: note = f"{abs(diff_days)}日前"
    
    return actual_date, price, note

# --- 日付ルールの計算 ---

def get_futures_delivery(year, month):
    """日本市場のSQ日：第2金曜日 (期货/SQ相当)"""
    c = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in c if week[4] != 0]
    return datetime.datetime(year, month, fridays[1]) if len(fridays) >= 2 else None

def get_option_delivery(year, month):
    """米国/国際市場のオプション交割日：第3金曜日"""
    c = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in c if week[4] != 0]
    return datetime.datetime(year, month, fridays[2]) if len(fridays) >= 3 else None

def get_month_end(year, month):
    """月末の最終日"""
    _, last_day = calendar.monthrange(year, month)
    return datetime.datetime(year, month, last_day)

def get_mid_month(year, month):
    """月中の15日"""
    return datetime.datetime(year, month, 15)

# ==========================================
#                メイン画面ロジック
# ==========================================

def render_jp_ui():
    st.markdown("### 📈 国際株式クオンツ分析ツール")

    # タブを使用して機能を切り替え
    tab1, tab2, tab3 = st.tabs(["🔍 基礎照会 (特定日株価)", "📊 戦略検証 (波段 vs 長持)", "🏆 ランキング"])

    # ----------------------------------------------------------------
    # 機能一：基礎照会 (原本の機能を保持)
    # ----------------------------------------------------------------
    with tab1:
        col1_input, col1_result = st.columns([1, 3], gap="large")
        
        with col1_input:
            with st.container(border=True):
                st.caption("照会設定")
                t1_code = st.text_input("銘柄コード", value="7974.T", key="t1_code_jp")
                cur_year = datetime.datetime.now().year
                t1_year = st.number_input("年度", min_value=2000, max_value=cur_year, value=cur_year, key="t1_year_jp")
                
                t1_mode_sel = st.radio(
                    "日付モード",
                    ("A: 月中(15日) & 月末", "B: SQ日(第2金曜) & オプション(第3金曜)"),
                    key="t1_mode_jp"
                )
                t1_run = st.button("株価照会", type="primary", use_container_width=True, key="t1_btn_jp")

        with col1_result:
            if t1_run and t1_code:
                with st.spinner('照会中...'):
                    # yfinanceの形式に合わせて日付を調整
                    df = get_stock_data(t1_code, f"{t1_year}-01-01", f"{t1_year}-12-31")
                    if df is not None:
                        target_list = []
                        mode = "A" if "A:" in t1_mode_sel else "B"
                        
                        for m in range(1, 13):
                            today = datetime.datetime.now()
                            dates_to_check = []
                            
                            if mode == "A":
                                dates_to_check = [
                                    ("月中", get_mid_month(t1_year, m)), 
                                    ("月末", get_month_end(t1_year, m))
                                ]
                            else:
                                f_day = get_futures_delivery(t1_year, m)
                                o_day = get_option_delivery(t1_year, m)
                                if f_day: dates_to_check.append(("SQ日(第2金曜)", f_day))
                                if o_day: dates_to_check.append(("オプション(第3金曜)", o_day))
                            
                            for type_name, dt in dates_to_check:
                                if dt <= today:
                                    act_date, price, note = get_nearest_price_info(dt, df)
                                    if price is not None:
                                        target_list.append({
                                            "月": f"{dt.strftime('%m')}月",
                                            "タイプ": type_name,
                                            "目標日付": dt.strftime("%Y-%m-%d"),
                                            "実際の取引日": act_date.strftime("%Y-%m-%d"),
                                            "終値": f"{float(price):.2f}",
                                            "説明": note
                                        })
                        
                        if target_list:
                            res_df = pd.DataFrame(target_list)
                            st.dataframe(res_df, use_container_width=True)
                            csv = res_df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 CSVエクスポート", csv, f"{t1_code}_{t1_year}_基礎照会.csv", "text/csv")
                        else:
                            st.info("該当する日付の履歴データがありません。")
                    else:
                        st.error("データ取得に失敗しました。銘柄コードを確認してください。")

    # ----------------------------------------------------------------
    # 機能二：戦略検証 (原本のロジックを完全移植)
    # ----------------------------------------------------------------
    with tab2:
        col2_input, col2_result = st.columns([1, 3], gap="large")
        
        with col2_input:
            with st.container(border=True):
                st.caption("検証パラメータ")
                t2_code = st.text_input("銘柄コード", value="7974.T", key="t2_code_jp")
                t2_year = st.number_input("検証年度", min_value=2010, max_value=cur_year, value=cur_year-1, key="t2_year_jp")
                
                st.divider()
                
                buy_rule = st.selectbox("🔵 買いポイント", 
                    ["SQ日(第2金曜)", "オプション(第3金曜)", "月末最終取引日"], key="buy_rule_jp")
                
                sell_rule = st.selectbox("🔴 売りポイント", 
                    ["翌月第1取引日", "翌月15日(または直近取引日)"], key="sell_rule_jp")
                
                t2_run = st.button("検証開始", type="primary", use_container_width=True, key="t2_btn_jp")

        with col2_result:
            if t2_run and t2_code:
                with st.spinner('リターンを計算中...'):
                    df = get_stock_data(t2_code, f"{t2_year}-01-01", f"{t2_year+1}-03-01")
                    
                    if df is not None:
                        trades = []
                        df['Year'] = df['日付'].dt.year
                        df['Month'] = df['日付'].dt.month
                        
                        for m in range(1, 13):
                            b_date, b_price = None, None
                            s_date, s_price = None, None
                            
                            curr_month_df = df[(df['Year'] == t2_year) & (df['Month'] == m)]
                            
                            if not curr_month_df.empty:
                                if "最終取引日" in buy_rule:
                                    row = curr_month_df.iloc[-1]
                                    b_date, b_price = row['日付'], row['終値']
                                else:
                                    target_buy = None
                                    if "SQ日" in buy_rule: target_buy = get_futures_delivery(t2_year, m)
                                    elif "オプション" in buy_rule: target_buy = get_option_delivery(t2_year, m)
                                    
                                    if target_buy:
                                        nearest_idx = (curr_month_df['日付'] - target_buy).abs().idxmin()
                                        b_date = curr_month_df.loc[nearest_idx, '日付']
                                        b_price = curr_month_df.loc[nearest_idx, '終値']
                            
                            if b_date: 
                                next_y = t2_year if m < 12 else t2_year + 1
                                next_m = m + 1 if m < 12 else 1
                                next_month_df = df[(df['Year'] == next_y) & (df['Month'] == next_m)]
                                
                                if not next_month_df.empty:
                                    if "第1取引日" in sell_rule:
                                        row = next_month_df.iloc[0]
                                        s_date, s_price = row['日付'], row['終値']
                                    else:
                                        target_sell = datetime.datetime(next_y, next_m, 15)
                                        nearest_idx = (next_month_df['日付'] - target_sell).abs().idxmin()
                                        s_date = next_month_df.loc[nearest_idx, '日付']
                                        s_price = next_month_df.loc[nearest_idx, '終値']
                                
                                if s_date and s_price:
                                    if s_date > b_date:
                                        trades.append({
                                            "月": f"{m}月",
                                            "買付日": b_date.strftime("%Y-%m-%d"),
                                            "買付価格": b_price,
                                            "売却日": s_date.strftime("%Y-%m-%d"),
                                            "売却価格": s_price,
                                            "損益": s_price - b_price
                                        })
                        
                        if trades:
                            t_df = pd.DataFrame(trades)
                            first_buy = t_df.iloc[0]['買付価格']
                            last_sell = t_df.iloc[-1]['売却価格']
                            total_profit = t_df['損益'].sum()
                            
                            yield_strategy = (total_profit / first_buy) * 100
                            yield_hold_real = (last_sell / first_buy - 1) * 100
                            hold_profit = last_sell - first_buy
                            
                            st.success(f"検証完了：{t2_code} ({t2_year})")
                            k1, k2, k3 = st.columns(3)
                            k1.metric("初期投資", f"{float(first_buy):.2f}")
                            k2.metric("戦略収益率 (波段)", f"{yield_strategy:.2f}%", delta=f"{total_profit:.2f}")
                            k3.metric("長期保有収益率 (死守)", f"{yield_hold_real:.2f}%", delta=f"{hold_profit:.2f}")
                            
                            st.markdown("---")
                            display_df = t_df.copy()
                            cols = ['買付価格', '売却価格', '損益']
                            for c in cols: display_df[c] = display_df[c].apply(lambda x: f"{float(x):.2f}")
                            
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            csv = display_df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 結果エクスポート", csv, f"{t2_code}_戦略検証.csv", "text/csv")
                        else:
                            st.warning(f"該当年度 ({t2_year}) のデータが不足しているか、取引が成立しませんでした。")

    # ----------------------------------------------------------------
    # Tab 3: ランキング (原本を継承)
    # ----------------------------------------------------------------
    with tab3:
        st.info("💡 注意：このページはローカルで生成されたスキャンファイルのみを表示します。")
        col3_left, col3_right = st.columns([1, 4])
        with col3_left:
            dataset = st.radio("📊 データセット選択", ["日経225 (N225)", "TOPIX 100"])
            scan_year = st.number_input("スキャン年度", min_value=2020, max_value=2026, value=2024, step=1, key="scan_year_jp")
            target_file = f"{'N225' if '225' in dataset else 'TOPIX100'}_Scan_{scan_year}.csv"
            st.write(f"対象ファイル: `{target_file}`")

        with col3_right:
            if os.path.exists(target_file):
                try:
                    df_rank = pd.read_csv(target_file)
                    st.success(f"✅ ファイルの読み込みに成功しました。計 {len(df_rank)} 件。")
                    st.subheader("🏆 スイング推奨ランキング（未完成）")
                    st.dataframe(df_rank.head(10), use_container_width=True)
                    with st.expander("全データを表示"):
                        st.dataframe(df_rank, use_container_width=True)
                except Exception as e:
                    st.error(f"読み込みエラー: {e}")
            else:
                st.warning(f"⚠️ ファイル `{target_file}` が見つかりません。")