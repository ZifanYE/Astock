import streamlit as st
import akshare as ak
import pandas as pd
import datetime
from calendar import monthrange

# 1. 设置页面布局为 wide，这样电脑上看才有"侧边栏"的感觉
st.set_page_config(page_title="A股特定日期收盘价查询", layout="wide")

# --- 函数定义部分 (保持不变) ---
def get_trading_data(symbol, start_date, end_date):
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return None
        df['日期'] = pd.to_datetime(df['日期'])
        return df[['日期', '收盘']]
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return None

def get_nearest_date(target_date, available_dates):
    nearest_idx = (available_dates - target_date).abs().idxmin()
    nearest_date = available_dates[nearest_idx]
    diff_days = (nearest_date - target_date).days
    return nearest_date, diff_days

def generate_target_dates(year):
    targets = []
    today = datetime.datetime.now()
    for month in range(1, 13):
        mid_date = datetime.datetime(year, month, 15)
        _, last_day = monthrange(year, month)
        end_date = datetime.datetime(year, month, last_day)
        
        if mid_date > today: break
        targets.append({"type": "月中", "date": mid_date})
        if end_date > today: break
        targets.append({"type": "月底", "date": end_date})
    return targets

# --- 页面 UI 部分 (主要修改了这里) ---

st.title("📈 A股特定日期收盘价查询")

# 创建两列布局
# 电脑上：col_input 在左(占1份宽)，col_result 在右(占3份宽)
# 手机上：col_input 会自动挤到最上面，col_result 在下面
col_input, col_result = st.columns([1, 3], gap="large")

# --- 左侧（或手机上方）：输入区 ---
with col_input:
    # 加一个边框容器，让它看起来更像一个独立的控制面板
    with st.container(border=True):
        st.subheader("🛠️ 查询设置")
        
        stock_code = st.text_input("股票代码", value="600519", help="例如: 600519")
        
        current_year = datetime.datetime.now().year
        year = st.number_input("年份", min_value=2000, max_value=current_year, value=current_year)
        
        # use_container_width=True 让按钮在手机上自动填满宽度，更易点击
        run_btn = st.button("开始查询", type="primary", use_container_width=True)
        
        st.caption("逻辑：自动寻找每月15日和月底。若不开盘则匹配最近交易日。")

# --- 右侧（或手机下方）：结果展示区 ---
with col_result:
    if run_btn and stock_code:
        with st.spinner('正在获取数据...'):
            start_date_str = f"{year}0101"
            end_date_str = f"{year}1231"
            
            df_hist = get_trading_data(stock_code, start_date_str, end_date_str)
            
            if df_hist is not None and not df_hist.empty:
                trading_dates = df_hist['日期']
                target_list = generate_target_dates(year)
                result_data = []
                
                for item in target_list:
                    t_date = item['date']
                    
                    actual_date, diff = get_nearest_date(t_date, trading_dates)
                    price = df_hist.loc[df_hist['日期'] == actual_date, '收盘'].values[0]
                    
                    note = "当日交易"
                    if diff > 0: note = f"延后{diff}天"
                    elif diff < 0: note = f"提前{abs(diff)}天"

                    result_data.append({
                        # 这里应用了之前的修复：不使用 %m月
                        "月份": f"{t_date.strftime('%m')}月", 
                        "类型": item['type'],
                        "目标日期": t_date.strftime("%Y-%m-%d"),
                        "实际交易日": actual_date.strftime("%Y-%m-%d"),
                        "收盘价": f"{price:.2f}",
                        "说明": note
                    })
                
                st.success(f"查询完成：{stock_code}")
                
                res_df = pd.DataFrame(result_data)
                
                # 展示表格
                st.dataframe(res_df, use_container_width=True)
                
                # 下载按钮
                csv = res_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 导出 CSV",
                    data=csv,
                    file_name=f"{stock_code}_{year}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("未找到数据，请检查代码。")
    else:
        # 当还没有查询时的占位提示
        st.info("👈 请在左侧（或上方）输入股票代码并点击查询")