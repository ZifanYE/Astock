# app.py
import streamlit as st
from streamlit_javascript import st_javascript
import engine_cn  # 中国市場向けエンジン
import engine_jp  # 国際市場向けエンジン

# =============================================================================
# ページ基本設定 (Page Configuration)
# =============================================================================
st.set_page_config(page_title="Quant Analysis Terminal", layout="wide")

# =============================================================================
# UIカスタマイズ CSS (UI Customization)
# =============================================================================
st.markdown("""
    <style>
        /* サイドバーを完全に非表示にする */
        [data-testid="stSidebar"] { display: none; }
        /* メインコンテンツエリアの上部余白を極限まで削る */
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 0rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        /* ヘッダー(メニュー)を非表示 */
        [data-testid="stHeader"] { display: none; }
        /* ボタンの配置を調整 */
        .stButton button {
            border-radius: 5px;
            padding: 2px 10px;
        }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 言語検知とセッション管理 (Language Detection & Session State)
# =============================================================================

# ブラウザ言語を取得 (Navigator.language)
browser_lang = st_javascript("navigator.language")

# セッション状態の初期化
if "lang_mode" not in st.session_state:
    st.session_state.lang_mode = None

# 初回アクセス時のみ自動判定を実行
if st.session_state.lang_mode is None and browser_lang:
    if "ja" in browser_lang.lower():
        st.session_state.lang_mode = "JP"
    else:
        st.session_state.lang_mode = "CN"

# 万が一取得できない場合のデフォルト値
if st.session_state.lang_mode is None:
    st.session_state.lang_mode = "CN"

# =============================================================================
# 右上角切り替えボタン (Top Right Language Toggle)
# =============================================================================
# タイトル行と同じ高さに切り替えボタンを配置
head_col1, head_col2 = st.columns([10, 1])

with head_col2:
    # 現在のモードの反対をボタンに表示
    toggle_label = "日/中"
    if st.button(toggle_label, help="Switch Language / 言語切り替え"):
        # モードを反転させる
        st.session_state.lang_mode = "JP" if st.session_state.lang_mode == "CN" else "CN"
        st.rerun()

# =============================================================================
# エンジンの実行 (Execution)
# =============================================================================
if st.session_state.lang_mode == "JP":
    # 日本語モード (International)
    engine_jp.render_jp_ui()
else:
    # 中国語モード (A-Share)
    engine_cn.render_cn_ui()