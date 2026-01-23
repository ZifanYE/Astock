# app.py
import streamlit as st
from streamlit_javascript import st_javascript
import engine_cn
import engine_jp
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
# 1. URLパラメータが存在すればそれを優先
# 2. 次にJavaScriptの取得結果に基づいて判定
# 3. 取得待ちの状態では初期値を設定しない（Race Condition対策）
if st.session_state.lang_mode is None:
    if url_lang == "jp":
        st.session_state.lang_mode = "JP"
    elif browser_lang: # JavaScriptの実行結果が返ってきた場合
        if "ja" in browser_lang.lower():
            st.session_state.lang_mode = "JP"
        else:
            st.session_state.lang_mode = "CN"
    else:
        # 非同期処理の遅延中は判定を保留
        pass

# =============================================================================
# 3. 右上部の言語切り替えボタン (日/中 トグル)
# =============================================================================
# タイトル行と同じ高さにボタンを配置するためのカラムレイアウト
h_col1, h_col2 = st.columns([12, 1])
with h_col2:
    if st.button("日/中"):
        # 未初期化状態でのクリックを考慮し、現在のステータスを反転させる
        current = st.session_state.lang_mode if st.session_state.lang_mode else "CN"
        st.session_state.lang_mode = "JP" if current == "CN" else "CN"
        # 状態変更後に即時再レンダリングを実行
        st.rerun()

# =============================================================================
# 4. エンジンの実行とルーティング
# =============================================================================
# 最終的なフォールバック：検知が完了していない場合はデフォルト(CN)を使用
final_mode = st.session_state.lang_mode if st.session_state.lang_mode else "CN"

if final_mode == "JP":
    # 日本市場向けエンジン (engine_jp.py) を実行
    engine_jp.render_jp_ui()
else:
    # 中国市場向けエンジン (engine_cn.py) を実行
    engine_cn.render_cn_ui()