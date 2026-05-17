import streamlit as st
import numpy as np
import pandas as pd
import time

# ==========================================
# 0. 核心算法：卡尔曼滤波 (预测与自动纠错)
# ==========================================
class KalmanFilterBot:
    """
    这是一个极简的卡尔曼滤波实现。
    它的核心思想完全符合你的要求：根据上一期的预测误差，动态调整对下一期的预测。
    """
    def __init__(self, process_variance=1e-5, estimated_measurement_variance=0.01):
        self.posteri_estimate = 1.0 # 初始猜测值
        self.posteri_error_estimate = 1.0 # 初始误差估计
        self.Q = process_variance # 过程噪音方差 (系统的不确定性)
        self.R = estimated_measurement_variance # 测量噪音方差

    def update(self, measurement):
        # 1. 预测阶段 (Predict)
        priori_estimate = self.posteri_estimate
        priori_error_estimate = self.posteri_error_estimate + self.Q

        # 2. 纠错阶段 (Update/Correct)
        blending_factor = priori_error_estimate / (priori_error_estimate + self.R) # 卡尔曼增益
        # 核心逻辑：当前估计 = 预测值 + 增益 * (实际值 - 预测值)[即误差]
        self.posteri_estimate = priori_estimate + blending_factor * (measurement - priori_estimate)
        self.posteri_error_estimate = (1 - blending_factor) * priori_error_estimate

        return self.posteri_estimate

# ==========================================
# 1. 状态初始化 (在全局最外层执行)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "bots" not in st.session_state:
    st.session_state.bots = [] # 存储活跃的机器人列表

def render_quant_ui():
    # ==========================================
    # 2. 登录模块
    # ==========================================
    if not st.session_state.logged_in:
        st.title("🔐 智能量化终端登录")
        with st.form("login_form"):
            user = st.text_input("用户名", placeholder="admin")
            pwd = st.text_input("密码", type="password", placeholder="123456")
            submitted = st.form_submit_button("登录")
            if submitted:
                if user == "admin" and pwd == "123456":
                    st.session_state.logged_in = True
                    st.success("登录成功！正在进入控制台...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("用户名或密码错误！(测试账号: admin / 123456)")
        return # 拦截未登录用户

    # ==========================================
    # 3. 主控制台模块 (已登录)
    # ==========================================
    st.title("🤖 Agentic Quant 机器人控制台")
    st.markdown("---")

    col1, col2 = st.columns([1, 2])

    # --- 左侧：机器人创建面板 ---
    with col1:
        st.subheader("🛠️ 创建新机器人")
        bot_name = st.text_input("机器人名称", placeholder="例如：Alpha-01")
        target_asset = st.selectbox("监控标的", ["沪深300 (000300)", "纳指ETF (513100)", "黄金ETF (518880)"])
        strategy = st.selectbox("驱动策略", [
            "卡尔曼滤波 (误差自适应预测)", 
            "LSTM深度学习 (需要GPU)", 
            "20日动量轮动"
        ])
        
        if st.button("🚀 部署上线"):
            if bot_name:
                new_bot = {
                    "id": len(st.session_state.bots) + 1,
                    "name": bot_name,
                    "asset": target_asset,
                    "strategy": strategy,
                    "status": "运行中 🟢",
                    # 为这个机器人实例化一个专属的预测引擎
                    "engine": KalmanFilterBot() 
                }
                st.session_state.bots.append(new_bot)
                st.success(f"{bot_name} 部署成功！")
                st.rerun()
            else:
                st.warning("请填写机器人名称")

        if st.button("🚪 退出登录"):
            st.session_state.logged_in = False
            st.rerun()

    # --- 右侧：机器人运行状态与纠错面板 ---
    with col2:
        st.subheader("📈 在线机器人监控")
        
        if not st.session_state.bots:
            st.info("当前没有运行中的机器人，请在左侧创建。")
        else:
            for bot in st.session_state.bots:
                with st.expander(f"[{bot['status']}] {bot['name']} | 标的: {bot['asset']} | 策略: {bot['strategy']}", expanded=True):
                    
                    # 生成模拟的最新市场数据
                    latest_actual_price = np.random.normal(1.0, 0.05) 
                    
                    # 调用机器人的算法进行“纠错与预测”
                    predicted_price = bot["engine"].update(latest_actual_price)
                    error_margin = abs((predicted_price - latest_actual_price) / latest_actual_price)

                    # UI 展示
                    m1, m2, m3 = st.columns(3)
                    m1.metric("市场实际最新价", f"{latest_actual_price:.4f}")
                    m2.metric("Bot 修正后预测价", f"{predicted_price:.4f}", delta=f"拟合追踪中", delta_color="normal")
                    m3.metric("当前预测误差", f"{error_margin:.2%}", delta="自动纠偏生效" if error_margin < 0.05 else "误差偏大", delta_color="inverse")
                    
                    # 模拟交易决策
                    if predicted_price > latest_actual_price * 1.01:
                        st.write("📢 **Bot 决策指令:** 预测价格高于现价，执行 **[买入操作]**")
                    elif predicted_price < latest_actual_price * 0.99:
                        st.write("📢 **Bot 决策指令:** 预测价格低于现价，执行 **[卖出平仓]**")
                    else:
                        st.write("📢 **Bot 决策指令:** 预测价格与现价接近，执行 **[观望]**")