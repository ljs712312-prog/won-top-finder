import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="원탑부동산 지번 역추적기 PRO+", layout="wide")

# --- [메인 프로그램 시작] ---
st.title("🕵️‍♂️ 원탑부동산 실거래가 지번 역추적기 (다중파일 지원)")

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
    uploaded_files = st.file_uploader("👉 분석할 엑셀/CSV 파일을 한 번에 여러 개 올려주세요 (최대 4개 권장).", type=['xlsx', 'csv'], accept_multiple_files=True)

    if uploaded_files:
        user_df = None
        
        # [PRO 엔진 업데이트] 로딩바 추가 및 초고속 헤더 스캔
        with st.spinner('파일 병합 및 구조 분석 중입니다... 잠시만 기다려주세요 ⏳'):
            try:
                df_list = []
                for uf in uploaded_files:
                    file_bytes = uf.getvalue() # 메모리에 올려서 속도 향상
                    skip_idx = 0
                    found = False
                    
                    # 엑셀 통째로 읽지 않고 껍데기(nrows=0)만 스캔해서 속도 10배 향상
                    for i in range(20):
                        try:
                            if uf.name.endswith('.csv'):
                                t_df = pd.read_csv(io.BytesIO(file_bytes), skiprows=i, nrows=0, encoding='cp949')
                            else:
                                t_df = pd.read_excel(io.BytesIO(file_bytes), skiprows=i, nrows=0)
                            
                            if any("도로명" in str(col) for col in t_df.columns):
                                skip_idx = i
                                found = True
                                break
                        except:
                            pass
                    
                    if found:
                        # 시작점을 찾았을 때만 진짜 데이터를 한 번만 로드
                        if uf.name.endswith('.csv'):
                            temp_df = pd.read_csv(io.BytesIO(file_bytes), skiprows=skip_idx, encoding='cp949')
                        else:
                            temp_df = pd.read_excel(io.BytesIO(file_bytes), skiprows=skip_idx)
                        
                        temp_df['출처파일'] = uf.name
                        df_list.append(temp_df)

                if df_list:
                    user_df = pd.concat(df_list, ignore_index=True)
            except Exception as e:
                st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        
        if user_df is None or user_df.empty:
            st.error("올려주신 파일들에서 올바른 데이터 형식을 찾을 수 없습니다. ('도로명' 열이 필요합니다)")
            st.stop()
        
        st.success(f"🎉 총 {len(uploaded_files)}개의 파일, {len(user_df)}건의 통합 데이터 분석 준비 완료!")
        
        def find_col_index(cols, keyword):
            for i, c in enumerate(cols):
                if keyword in str(c): return i
            return 0
            
        def get_col_name(cols, keyword):
            for c in cols:
                if keyword in str(c): return c
            return None

        # --- 분석 조건 인터페이스 ---
        st.write("📋 분석 조건 (필수 4개 열만 확인해주세요):")
        c1, c2, c3, c4 = st.columns(4)
        with c1: col_road = st.selectbox("도로명 열", user_df.columns, index=find_col_index(user_df.columns, "도로명"))
        with c2: col_jibun = st.selectbox("번지 열", user_df.columns, index=find_col_index(user_df.columns, "번지"))
        with c3: col_year = st.selectbox("건축년도 열", user_df.columns, index=find_col_index(user_df.columns, "건축년도"))
        with c4: col_area = st.selectbox("면적 열", user_df.columns, index=find_col_index(user_df.columns, "면적"))

        col_sigungu = get_col_name(user_df.columns, "시군구")
        col_contract = get_col_name(user_df.columns, "계약기간")

        target_period = st.text_input("🔍 찾고 싶은 계약 기간 (예: 202611 입력 시 해당 월 포함된 행만 필터링)", "")

        if st.button("🚀 다중 파일 통합 역추적 시작"):
            # 계약기간 필터 적용 (열이 존재할 경우에만)
            if target_period and col_contract:
                working_df = user_df[user_df[col_contract].astype(str).str.contains(target_period, na=False)]
                st.info(f"검색어 '{target_period}'가 포함된 {len(working_df)}건의 데이터를 추려냈습니다.")
            elif target_period and not col_contract:
                st.warning("'계약기간' 열을 자동으로 찾을 수 없어 전체 데이터를 분석합니다.")
                working_df = user_df
            else:
                working_df = user_df
                st.info("조건 없이 전체 데이터를 분석합니다.")

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
                    
                    # 시군구 데이터에서 '동' 이름 자동 추출 (열이 없으면 공백 처리)
                    raw_sigungu = str(row[col_sigungu]).strip() if col_sigungu else ""
                    dong_name = raw_sigungu.split()[-1] if ' ' in raw_sigungu else raw_sigungu
                    
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
                        
                        # 결과 정리: 동 이름 + 번지 조합으로 리스트 생성 ('번지' 텍스트 제거)
                        found_list = candidates['platPlc'].unique().tolist()
                        if dong_name:
                            clean_list = [f"{dong_name} {str(j).split()[-1].replace('번지', '')}" for j in found_list]
                        else:
                            clean_list = [str(j).split()[-1].replace('번지', '') for j in found_list]
                        
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
                # 보기 편하게 출처파일을 맨 앞으로 이동
                cols = result_df.columns.tolist()
                cols.insert(0, cols.pop(cols.index('출처파일')))
                result_df = result_df[cols]

                st.success(f"🎉 총 {len(result_df)}건 역추적 분석 완료!")
                st.dataframe(result_df)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    result_df.to_excel(writer, index=False)
                st.download_button("📥 통합 분석 결과 다운로드 (엑셀)", output.getvalue(), "원탑_통합_지번추적_결과.xlsx")
