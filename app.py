# app.py  python -m streamlit run app.py
import streamlit as st
from streamlit_javascript import st_javascript
import engine_cn
import engine_jp
import quant_engine  # [新增] 引入量化模块
import time

# =============================================================================
# 1. ページ構成とUIレイアウトの最適化 (CSS)
# =============================================================================
# ページ設定：タイトルおよびワイドレイアウトの有効化
st.set_page_config(page_title="Quant Analysis Terminal", layout="wide")

# CSSインジェクション：サイドバーの非表示、上部余白の最小化、ヘッダーの削除
st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { display: none; }
        .block-container {
            padding-top: 0.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# [新增] 初始化页面路由状态
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"

# =============================================================================
# 2. 言語検知ロジック (URLパラメータ > JavaScript検知)
# =============================================================================

# URLパラメータの確認 (例: ?lang=jp)
# クエリパラメータによる強制ルーティングを最優先する
url_lang = st.query_params.get("lang", "").lower()

# JavaScript経由でブラウザの言語設定 (navigator.language) を取得
browser_lang = st_javascript("navigator.language")

# セッション状態 (st.session_state) の初期化
if "lang_mode" not in st.session_state:
    st.session_state.lang_mode = None

# 言語判定ロジック：
if st.session_state.lang_mode is None:
    if url_lang == "jp":
        st.session_state.lang_mode = "JP"
    elif browser_lang: # JavaScriptの実行結果が返ってきた場合
        if "ja" in browser_lang.lower():
            st.session_state.lang_mode = "JP"
        else:
            st.session_state.lang_mode = "CN"
    else:
        pass

# =============================================================================
# 3. 右上部の言語切り替えボタン (日/中 トグル) & 量化跳转 [修改]
# =============================================================================
# [修改] 调整列比例以容纳两个按钮 (从 [12, 1] 变为 [10, 1, 1])
h_col1, h_col2, h_col3 = st.columns([10, 1, 1])

# [新增] 量化页面跳转按钮
with h_col2:
    btn_label = "量化交易" if st.session_state.current_page == "home" else "返回行情"
    if st.button(btn_label):
        st.session_state.current_page = "quant" if st.session_state.current_page == "home" else "home"
        st.rerun()

# [修改] 原语言切换按钮移至 h_col3
with h_col3:
    if st.button("日/中"):
        current = st.session_state.lang_mode if st.session_state.lang_mode else "CN"
        st.session_state.lang_mode = "JP" if current == "CN" else "CN"
        st.rerun()

# =============================================================================
# 4. エンジンの実行とルーティング [修改]
# =============================================================================
final_mode = st.session_state.lang_mode if st.session_state.lang_mode else "CN"

# [修改] 增加最外层的页面路由拦截
if st.session_state.current_page == "quant":
    quant_engine.render_quant_ui()  # [新增] 渲染量化页面
else:
    # 保持原有逻辑
    if final_mode == "JP":
        engine_jp.render_jp_ui()
    else:
        engine_cn.render_cn_ui()