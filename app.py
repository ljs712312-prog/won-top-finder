import streamlit as st
import pandas as pd
import io

# --- [관리자 보안 설정] ---
try:
    ADMIN_PASSWORD = st.secrets["password"]
except:
    ADMIN_PASSWORD = "0901" 
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

# 2. 메인 프로그램 시작
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
            # [핵심 수정] 안내 문구를 건너뛰고 진짜 헤더를 찾는 로직
            found_df = None
            for i in range(20):  # 상단 20줄까지 탐색
                uploaded_file.seek(0)
                if uploaded_file.name.endswith('.csv'):
                    df_test = pd.read_csv(uploaded_file, skiprows=i, encoding='cp949')
                else:
                    df_test = pd.read_excel(uploaded_file, skiprows=i)
                
                # 컬럼명 중에 '도로명'이 정확히 포함된 줄이 나오면 멈춤
                if any("도로명" in str(col) for col in df_test.columns):
                    found_df = df_test
                    break
            
            if found_df is not None:
                user_df = found_df
            else:
                # 못 찾을 경우 기본 읽기
                uploaded_file.seek(0)
                user_df = pd.read_csv(uploaded_file, encoding='cp949') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

            st.success("파일 읽기 성공! 분석 조건을 확인해주세요.")
            
            st.write("📋 분석 조건 설정:")
            def get_idx(cols, key):
                for i, c in enumerate(cols):
                    if key in str(c): return i
                return 0

            c1, c2, c3, c4 = st.columns(4)
            with c1: col_road = st.selectbox("도로명 열", user_df.columns, index=get_idx(user_df.columns, "도로명"))
            with c2: col_jibun = st.selectbox("번지 열", user_df.columns, index=get_idx(user_df.columns, "번지"))
            with c3: col_year = st.selectbox("건축년도 열", user_df.columns, index=get_idx(user_df.columns, "건축년도"))
            with c4: col_area = st.selectbox("면적 열", user_df.columns, index=get_idx(user_df.columns, "면적"))

            if st.button("🚀 역추적 시작"):
                results = []
                p_bar = st.progress(0)
                
                for i, row in user_df.iterrows():
                    raw_road = str(row[col_road]).strip()
                    target_road = raw_road.split(' ')[-1] if ' ' in raw_road else raw_road
                    raw_year = str(row[col_year]).strip()[:4]
                    target_area = float(row[col_area]) if pd.notnull(row[col_area]) else 0
                    
                    # 검색 로직
                    cond = master_db['newPlatPlc'].str.contains(target_road, na=False)
                    candidates = master_db[cond]
                    
                    if not candidates.empty:
                        # 필터링 (년도 ±1, 면적 ±3%)
                        if raw_year.isdigit():
                            y = int(raw_year)
                            candidates = candidates[candidates['대장연도'].isin([str(y-1), str(y), str(y+1)])]
                        if target_area > 0:
                            candidates = candidates[
                                (candidates['totArea'] * 0.97 <= target_area) & 
                                (target_area <= candidates['totArea'] * 1.03)
                            ]
                        
                        clean_list = [str(j).split()[-1] for j in candidates['platPlc'].unique().tolist()]
                        res = row.to_dict()
                        res['유력지번'] = ", ".join(clean_list[:3])
                        res['신뢰도'] = '⭐⭐⭐' if len(clean_list) <= 2 else '⭐'
                        results.append(res)
                    else:
                        res = row.to_dict()
                        res['유력지번'] = '데이터없음'
                        results.append(res)
                    p_bar.progress((i + 1) / len(user_df))

                result_df = pd.DataFrame(results)
                st.success("🎉 분석 완료!")
                st.dataframe(result_df)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    result_df.to_excel(writer, index=False)
                st.download_button("📥 결과 다운로드", output.getvalue(), "역추적_결과.xlsx")
                
        except Exception as e:
            st.error(f"파일 처리 중 오류: {e}")