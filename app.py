import streamlit as st
import akshare as ak
import pandas as pd
import datetime
from calendar import monthrange

# 设置页面配置
st.set_page_config(page_title="A股特定日期收盘价查询", layout="wide")

def get_trading_data(symbol, start_date, end_date):
    """
    使用 Akshare 获取个股历史数据
    symbol: 股票代码 (如 "600519")
    """
    try:
        # adjust="qfq" 代表前复权，通常分析价格走势使用前复权
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty:
            return None
        
        # 确保日期列是 datetime 格式
        df['日期'] = pd.to_datetime(df['日期'])
        return df[['日期', '收盘']]
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return None

def get_nearest_date(target_date, available_dates):
    """
    在交易日列表中寻找离 target_date 最近的一天
    """
    # 计算所有可用日期与目标日期的绝对时间差
    # idxmin 会返回最小差异的索引
    nearest_idx = (available_dates - target_date).abs().idxmin()
    nearest_date = available_dates[nearest_idx]
    
    # 计算差异天数
    diff_days = (nearest_date - target_date).days
    return nearest_date, diff_days

def generate_target_dates(year):
    """
    生成当年的所有月中(15号)和月底日期
    """
    targets = []
    today = datetime.datetime.now()
    
    for month in range(1, 13):
        # 1. 月中：15号
        mid_date = datetime.datetime(year, month, 15)
        
        # 2. 月底：计算当月最后一天
        _, last_day = monthrange(year, month)
        end_date = datetime.datetime(year, month, last_day)
        
        # 如果日期在未来，则停止生成（不展示还没到的日子）
        if mid_date > today:
            break
        targets.append({"type": "月中", "date": mid_date})
        
        if end_date > today:
            break
        targets.append({"type": "月底", "date": end_date})
            
    return targets

# --- 页面 UI 部分 ---

st.title("📈 A股特定日期收盘价查询工具")
st.markdown("查询逻辑：自动寻找每月的 **15日** 和 **月底**。如果当日不开盘（周末/节假日），系统会自动匹配**最近的一个交易日**。")

# 侧边栏输入
with st.sidebar:
    st.header("查询设置")
    stock_code = st.text_input("输入股票代码 (6位数字)", value="600519", help="例如贵州茅台: 600519")
    year = st.number_input("选择年份", min_value=2000, max_value=datetime.datetime.now().year, value=datetime.datetime.now().year)
    run_btn = st.button("开始查询", type="primary")

if run_btn and stock_code:
    with st.spinner('正在从 Akshare 获取数据，请稍候...'):
        # 1. 准备时间范围 (整年)
        start_date_str = f"{year}0101"
        end_date_str = f"{year}1231"
        
        # 2. 获取数据
        df_hist = get_trading_data(stock_code, start_date_str, end_date_str)
        
        if df_hist is not None and not df_hist.empty:
            trading_dates = df_hist['日期']
            
            # 3. 生成目标日期列表
            target_list = generate_target_dates(year)
            
            result_data = []
            
            for item in target_list:
                t_date = item['date']
                t_type = item['type']
                
                # 寻找最近的交易日
                actual_date, diff = get_nearest_date(t_date, trading_dates)
                
                # 获取该日收盘价
                price = df_hist.loc[df_hist['日期'] == actual_date, '收盘'].values[0]
                
                # 备注信息
                note = ""
                if diff == 0:
                    note = "当日正常交易"
                elif diff > 0:
                    note = f"推后 {diff} 天 (如遇周末延后)"
                else:
                    note = f"提前 {abs(diff)} 天 (如遇周末提前)"

                result_data.append({
                    "月份": f"{t_date.strftime('%m')}月",
                    "类型": t_type,
                    "目标日期": t_date.strftime("%Y-%m-%d"),
                    "实际交易日": actual_date.strftime("%Y-%m-%d"),
                    "收盘价": f"{price:.2f}",
                    "说明": note
                })
            
            # 4. 展示结果
            st.success(f"查询成功：{stock_code} ({year}年)")
            
            res_df = pd.DataFrame(result_data)
            
            # 展示表格
            st.dataframe(res_df, use_container_width=True)
            
            # 提供下载按钮
            csv = res_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 导出结果为 CSV",
                data=csv,
                file_name=f"{stock_code}_{year}_收盘价.csv",
                mime="text/csv",
            )
            
        else:
            st.warning("未找到数据，请检查股票代码是否正确，或该年份该股票是否已上市。")