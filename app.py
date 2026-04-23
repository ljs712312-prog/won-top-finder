import streamlit as st
import pandas as pd
import io

# --- [관리자 설정 구역] ---
# 사무실 식구들에게 알려줄 비밀번호를 정하세요.
ADMIN_PASSWORD = "1584" 
# -----------------------

st.set_page_config(page_title="원탑부동산 지번 역추적기", layout="wide")

# 1. 로그인 체크
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 원탑부동산 전용 시스템")
    pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
    if st.button("로그인"):
        if pw == ADMIN_PASSWORD:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 2. 메인 프로그램 (로그인 성공 시에만 실행)
st.title("🕵️‍♂️ 원탑부동산 실거래가 지번 역추적기")

@st.cache_data
def load_db():
    try:
        # 데이터 로드 및 전처리
        df = pd.read_csv('suwon_building_master_v3.csv')
        df['대장연도'] = df['useAprDay'].astype(str).str[:4]
        df['totArea'] = pd.to_numeric(df['totArea'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"데이터베이스 로드 실패: {e}")
        return None

master_db = load_db()

if master_db is not None:
    uploaded_file = st.file_uploader("👉 분석할 엑셀/CSV 파일을 올려주세요.", type=['xlsx', 'csv'])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                user_df = pd.read_csv(uploaded_file, encoding='cp949')
            else:
                user_df = pd.read_excel(uploaded_file)
            
            st.success("파일 업로드 성공! 분석 시작 버튼을 눌러주세요.")
            
            if st.button("🚀 역추적 시작"):
                # (중략 - 기존의 정밀 역추적 로직이 실행됩니다)
                st.write("분석 중...")
                # ... 실제 분석 로직 ...