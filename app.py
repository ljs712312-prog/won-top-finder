import streamlit as st
import pandas as pd
import io

# --- [관리자 보안 설정] ---
# 스트림릿 Settings -> Secrets에 password를 설정했다면 아래 줄을 쓰세요.
# 만약 아직 설정 전이라면 ADMIN_PASSWORD = "원탑7788" 처럼 직접 적으셔도 됩니다.
try:
    ADMIN_PASSWORD = st.secrets["password"]
except:
    ADMIN_PASSWORD = "0901" # 설정 안 되었을 때의 비상용 비번
# -----------------------

st.set_page_config(page_title="원탑부동산 지번 역추적기", layout="wide")

# 1. 로그인 체크 로직
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
            
            # 국토부 양식 특유의 상단 빈 줄 제거 로직
            if "도로명" not in user_df.columns:
                for i in range(1, 10):
                    uploaded_file.seek(0)
                    test_df = pd.read_csv(uploaded_file, skiprows=i, encoding='cp949') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, skiprows=i)
                    if "도로명" in test_df.columns:
                        user_df = test_df
                        break

            st.write("📋 분석 조건 설정:")
            c1, c2, c3, c4 = st.columns(4)
            with c1: col_road = st.selectbox("도로명 열", user_df.columns, index=next((i for i, c in enumerate(user_df.columns) if "도로명" in str(c)), 0))
            with c2: col_jibun = st.selectbox("번지 열", user_df.columns, index=next((i for i, c in enumerate(user_df.columns) if "번지" in str(c)), 0))
            with c3: col_year = st.selectbox("건축년도 열", user_df.columns, index=next((i for i, c in enumerate(user_df.columns) if "건축년도" in str(c)), 0))
            with c4: col_area = st.selectbox("면적 열", user_df.columns, index=next((i for i, c in enumerate(user_df.columns) if "면적" in str(c)), 0))

            if st.button("🚀 역추적 시작"):
                results = []
                p_bar = st.progress(0)
                
                for i, row in user_df.iterrows():
                    # 데이터 보정 로직
                    raw_road = str(row[col_road]).strip()
                    target_road = raw_road.split(' ')[-1] if ' ' in raw_road else raw_road
                    raw_year = str(row[col_year]).strip()[:4]
                    target_area = float(row[col_area]) if pd.notnull(row[col_area]) else 0
                    
                    # 검색 시작
                    cond = master_db['newPlatPlc'].str.contains(target_road, na=False)
                    candidates = master_db[cond]
                    
                    if not candidates.empty:
                        # 건축년도 ±1년 필터링
                        if raw_year.isdigit():
                            y = int(raw_year)
                            candidates = candidates[candidates['대장연도'].isin([str(y-1), str(y), str(y+1)])]
                        
                        # 면적 ±3% 필터링
                        if target_area > 0:
                            candidates = candidates[
                                (candidates['totArea'] * 0.97 <= target_area) & 
                                (target_area <= candidates['totArea'] * 1.03)
                            ]
                        
                        found_list = candidates['platPlc'].unique().tolist()
                        clean_list = [str(j).split()[-1] for j in found_list]
                        
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
                st.download_button("📥 엑셀로 저장하기", output.getvalue(), "역추적_결과.xlsx")
                
        except Exception as e:
            st.error(f"파일 처리 중 오류: {e}")