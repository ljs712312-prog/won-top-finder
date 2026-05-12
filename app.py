import streamlit as st
import pandas as pd
import io

# --- [1. 관리자 보안 설정] ---
try:
    ADMIN_PASSWORD = st.secrets["password"]
except:
    ADMIN_PASSWORD = "1584" 
# ---------------------------

st.set_page_config(page_title="원탑부동산 지번 역추적기 PRO", layout="wide")

# [보안] 로그인 체크 로직
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

# --- [2. 메인 프로그램 시작] ---
st.title("🕵️‍♂️ 원탑부동산 실거래가 지번 역추적기 (계약기간 검색 + 동지번 표시)")

@st.cache_data
def load_db():
    try:
        # 수원시 마스터 DB 로드
        df = pd.read_csv('suwon_building_master_v3.csv')
        df['대장연도'] = df['useAprDay'].astype(str).str[:4]
        df['totArea'] = pd.to_numeric(df['totArea'], errors='coerce')
        df['archArea'] = pd.to_numeric(df['archArea'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"마스터 DB 로드 실패: {e}")
        return None

master_db = load_db()

if master_db is not None:
    uploaded_file = st.file_uploader("👉 분석할 엑셀/CSV 파일을 올려주세요.", type=['xlsx', 'csv'])

    if uploaded_file:
        try:
            # 헤더 자동 찾기 로직
            user_df = None
            for i in range(20):
                uploaded_file.seek(0)
                if uploaded_file.name.endswith('.csv'):
                    temp_df = pd.read_csv(uploaded_file, skiprows=i, encoding='cp949')
                else:
                    temp_df = pd.read_excel(uploaded_file, skiprows=i)
                
                if any("도로명" in str(col) for col in temp_df.columns):
                    user_df = temp_df
                    break
            
            if user_df is None:
                st.error("파일에서 '도로명' 열을 찾을 수 없습니다.")
                st.stop()

            st.success("파일 분석 준비 완료!")
            
            def find_col(cols, keyword):
                for i, c in enumerate(cols):
                    if keyword in str(c): return i
                return 0

            # --- 분석 조건 인터페이스 ---
            st.write("📋 분석 조건 및 필터 설정:")
            
            # 시군구 열을 추가로 받기 위해 컬럼을 6개로 분할
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1: col_sigungu = st.selectbox("시군구 열", user_df.columns, index=find_col(user_df.columns, "시군구"))
            with c2: col_road = st.selectbox("도로명 열", user_df.columns, index=find_col(user_df.columns, "도로명"))
            with c3: col_jibun = st.selectbox("번지 열", user_df.columns, index=find_col(user_df.columns, "번지"))
            with c4: col_year = st.selectbox("건축년도 열", user_df.columns, index=find_col(user_df.columns, "건축년도"))
            with c5: col_area = st.selectbox("면적 열", user_df.columns, index=find_col(user_df.columns, "면적"))
            with c6: col_contract = st.selectbox("계약기간 열", user_df.columns, index=find_col(user_df.columns, "계약기간"))

            # 계약기간 필터 입력 칸
            target_period = st.text_input("🔍 찾고 싶은 계약 기간 (예: 202611 입력 시 해당 월 포함된 행만 분석)", "")

            if st.button("🚀 유력지번 정밀 역추적 시작"):
                # 계약기간 필터 적용
                if target_period:
                    working_df = user_df[user_df[col_contract].astype(str).str.contains(target_period, na=False)]
                    st.info(f"검색어 '{target_period}'가 포함된 {len(working_df)}건의 데이터를 분석합니다.")
                else:
                    working_df = user_df
                    st.info("전체 데이터를 분석합니다.")

                if working_df.empty:
                    st.warning("입력하신 계약 기간과 일치하는 데이터가 없습니다.")
                else:
                    results = []
                    p_bar = st.progress(0)
                    
                    for i, (idx, row) in enumerate(working_df.iterrows()):
                        # 데이터 전처리
                        raw_road = str(row[col_road]).strip()
                        target_road = raw_road.split(' ')[-1] if ' ' in raw_road else raw_road
                        blind_jibun = str(row[col_jibun]).strip()
                        raw_year = str(row[col_year]).strip()[:4]
                        target_area = float(row[col_area]) if pd.notnull(row[col_area]) else 0
                        
                        # 시군구 데이터에서 '동' 이름만 추출 (예: '경기도 수원시 팔달구 화서동' -> '화서동')
                        raw_sigungu = str(row[col_sigungu]).strip()
                        dong_name = raw_sigungu.split()[-1] if ' ' in raw_sigungu else raw_sigungu
                        
                        # [PRO 엔진 핵심 로직]
                        # 1단계: 도로명 필터링
                        candidates = master_db[master_db['newPlatPlc'].str.contains(target_road, na=False)]
                        
                        if not candidates.empty:
                            # 2단계: 번지 앞자리 대조
                            first_digit = blind_jibun[0] if blind_jibun and blind_jibun[0].isdigit() else ""
                            if first_digit:
                                matched = candidates[candidates['platPlc'].str.contains(f" {first_digit}", na=False)]
                                if not matched.empty: candidates = matched

                            # 3단계: 건축년도 ±2년 대조
                            if raw_year.isdigit():
                                y = int(raw_year)
                                years_range = [str(y+off) for off in range(-2, 3)]
                                matched = candidates[candidates['대장연도'].isin(years_range)]
                                if not matched.empty: candidates = matched
                            
                            # 4단계: 면적 대조 ±3%
                            if target_area > 0:
                                matched = candidates[
                                    ((candidates['totArea'] * 0.97 <= target_area) & (target_area <= candidates['totArea'] * 1.03)) |
                                    ((candidates['archArea'] * 0.97 <= target_area) & (target_area <= candidates['archArea'] * 1.03))
                                ]
                                if not matched.empty: candidates = matched
                            
                            # 결과 정리: 동 이름 + 번지 조합으로 리스트 생성
                            found_list = candidates['platPlc'].unique().tolist()
                            clean_list = [f"{dong_name} {str(j).split()[-1]}" for j in found_list]
                            
                            res = row.to_dict()
                            res['추적_유력지번'] = ", ".join(clean_list[:3])
                            
                            # 신뢰도 평가
                            if len(clean_list) == 1:
                                res['신뢰도'] = '⭐⭐⭐ (확실)'
                            elif 1 <= len(clean_list) <= 3:
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
                        
                        p_bar.progress((i + 1) / len(working_df))

                    result_df = pd.DataFrame(results)
                    st.success(f"🎉 {len(result_df)}건 역추적 분석 완료!")
                    st.dataframe(result_df)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        result_df.to_excel(writer, index=False)
                    st.download_button("📥 분석 결과 다운로드 (엑셀)", output.getvalue(), "원탑_지번추적_결과.xlsx")
                    
        except Exception as e:
            st.error(f"오류 발생: {e}")
