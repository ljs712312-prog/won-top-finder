import streamlit as st
import pandas as pd
import io

# --- [1. 관리자 보안 설정] ---
try:
    ADMIN_PASSWORD = st.secrets["password"]
except:
    ADMIN_PASSWORD = "0901" 
# ---------------------------

st.set_page_config(page_title="원탑부동산 지번 역추적기", layout="wide")

# [보안] 로그인 체크
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

# --- [2. 메인 프로그램 (로그인 성공 시)] ---
st.title("🕵️‍♂️ 원탑부동산 실거래가 지번 역추적기 (PRO 엔진)")

@st.cache_data
def load_db():
    try:
        df = pd.read_csv('suwon_building_master_v3.csv')
        df['대장연도'] = df['useAprDay'].astype(str).str[:4]
        df['totArea'] = pd.to_numeric(df['totArea'], errors='coerce')
        df['archArea'] = pd.to_numeric(df['archArea'], errors='coerce') # [PRO] 건축면적 대조 부활
        return df
    except Exception as e:
        st.error(f"마스터 DB 로드 실패: {e}")
        return None

master_db = load_db()

if master_db is not None:
    uploaded_file = st.file_uploader("👉 분석할 엑셀/CSV 파일을 올려주세요.", type=['xlsx', 'csv'])

    if uploaded_file:
        try:
            # 상단 안내문구 자동 스킵
            user_df = None
            for i in range(15):
                uploaded_file.seek(0)
                if uploaded_file.name.endswith('.csv'):
                    temp_df = pd.read_csv(uploaded_file, skiprows=i, encoding='cp949')
                else:
                    temp_df = pd.read_excel(uploaded_file, skiprows=i)
                
                if any("도로명" in str(col) for col in temp_df.columns):
                    user_df = temp_df
                    break
            
            if user_df is None:
                st.error("파일에서 '도로명' 열을 찾을 수 없습니다. 양식을 확인해주세요.")
                st.stop()

            st.success("파일 분석 준비 완료!")
            
            def find_col(cols, keyword):
                for i, c in enumerate(cols):
                    if keyword in str(c): return i
                return 0

            st.write("📋 분석 조건 설정 (자동 매칭됨):")
            c1, c2, c3, c4 = st.columns(4)
            with c1: col_road = st.selectbox("도로명 열", user_df.columns, index=find_col(user_df.columns, "도로명"))
            with c2: col_jibun = st.selectbox("번지 열", user_df.columns, index=find_col(user_df.columns, "번지"))
            with c3: col_year = st.selectbox("건축년도 열", user_df.columns, index=find_col(user_df.columns, "건축년도"))
            with c4: col_area = st.selectbox("면적 열", user_df.columns, index=find_col(user_df.columns, "면적"))

            if st.button("🚀 유력지번 정밀 역추적 시작"):
                results = []
                p_bar = st.progress(0)
                
                for i, row in user_df.iterrows():
                    # 1. 입력값 보정
                    raw_road = str(row[col_road]).strip()
                    target_road = raw_road.split(' ')[-1] if ' ' in raw_road else raw_road
                    blind_jibun = str(row[col_jibun]).strip()
                    raw_year = str(row[col_year]).strip()[:4]
                    target_area = float(row[col_area]) if pd.notnull(row[col_area]) else 0
                    
                    # [1차] 도로명 일치 검색
                    candidates = master_db[master_db['newPlatPlc'].str.contains(target_road, na=False)]
                    
                    if not candidates.empty:
                        # [2차] 번지 앞자리 대조 (예: 5** 이면 5로 시작하는 번지만)
                        first_digit = blind_jibun[0] if blind_jibun and blind_jibun[0].isdigit() else ""
                        if first_digit:
                            matched_jibun = candidates[candidates['platPlc'].str.contains(f" {first_digit}", na=False)]
                            if not matched_jibun.empty: # 일치하는게 있을 때만 좁힘 (없으면 도로명 결과 유지)
                                candidates = matched_jibun

                        # [3차] 건축년도 대조 (±2년 허용으로 대폭 확대)
                        if raw_year.isdigit():
                            y = int(raw_year)
                            matched_year = candidates[candidates['대장연도'].isin([str(y-2), str(y-1), str(y), str(y+1), str(y+2)])]
                            if not matched_year.empty: # 오차 범위 내에 있으면 좁힘
                                candidates = matched_year
                        
                        # [4차] 면적 대조 (연면적 or 건축면적 중 하나라도 ±3% 이내면 합격)
                        if target_area > 0:
                            matched_area = candidates[
                                ((candidates['totArea'] * 0.97 <= target_area) & (target_area <= candidates['totArea'] * 1.03)) |
                                ((candidates['archArea'] * 0.97 <= target_area) & (target_area <= candidates['archArea'] * 1.03))
                            ]
                            if not matched_area.empty:
                                candidates = matched_area
                        
                        # 5. 결과 도출
                        found_list = candidates['platPlc'].unique().tolist()
                        clean_list = [str(j).split()[-1] for j in found_list]
                        
                        res = row.to_dict()
                        res['추적_유력지번'] = ", ".join(clean_list[:3])
                        
                        # 신뢰도 시스템
                        if len(clean_list) == 1:
                            res['신뢰도'] = '⭐⭐⭐ (확실)'
                        elif 1 < len(clean_list) <= 3:
                            res['신뢰도'] = '⭐⭐ (유력)'
                        elif len(clean_list) > 3:
                            res['신뢰도'] = '⭐ (후보많음)'
                        else:
                            res['추적_유력지번'] = '대조불가'
                            res['신뢰도'] = '❌'
                        results.append(res)
                    else:
                        res = row.to_dict()
                        res['추적_유력지번'] = '데이터없음'
                        res['신뢰도'] = '❌'
                        results.append(res)
                    
                    p_bar.progress((i + 1) / len(user_df))

                result_df = pd.DataFrame(results)
                st.success("🎉 역추적 분석 완료!")
                st.dataframe(result_df)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    result_df.to_excel(writer, index=False)
                st.download_button("📥 분석 결과 다운로드 (엑셀)", output.getvalue(), "원탑_지번추적_결과.xlsx")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")