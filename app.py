import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="원탑부동산 지번 역추적기 v4", layout="wide")

st.title("🕵️‍♂️ 원탑부동산 실거래가 지번 역추적기 (다중 단서 조합형)")
st.info("도로명, 번지앞자리, 건축년도를 기본으로 하며, 면적은 데이터 성격에 따라 유동적으로 반영합니다.")

@st.cache_data
def load_db():
    try:
        # 수원시 마스터 DB 로드
        df = pd.read_csv('suwon_building_master_v3.csv')
        # 사용승인일에서 연도 추출
        df['대장연도'] = df['useAprDay'].astype(str).str[:4]
        # 면적 데이터 숫자화
        df['totArea'] = pd.to_numeric(df['totArea'], errors='coerce') # 연면적
        df['archArea'] = pd.to_numeric(df['archArea'], errors='coerce') # 건축면적
        return df
    except:
        st.error("⚠️ 'suwon_building_master_v3.csv' 파일을 찾을 수 없습니다.")
        return None

master_db = load_db()

if master_db is not None:
    uploaded_file = st.file_uploader("👉 분석할 실거래가 엑셀/CSV 파일을 올려주세요.", type=['xlsx', 'csv'])

    if uploaded_file:
        try:
            # 국토부 양식(15줄 건너뛰기) 대응
            user_df = pd.read_csv(uploaded_file, skiprows=15, encoding='cp949') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, skiprows=15)
            
            # 만약 데이터가 안 읽혔다면(직접 편집한 파일 등) 0줄부터 다시 읽기
            if len(user_df.columns) < 5:
                uploaded_file.seek(0)
                user_df = pd.read_csv(uploaded_file, encoding='cp949') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

            st.write("📋 분석 조건 설정:")
            c1, c2, c3, c4 = st.columns(4)
            with c1: col_road = st.selectbox("도로명", user_df.columns, index=user_df.columns.get_loc('도로명') if '도로명' in user_df.columns else 0)
            with c2: col_jibun = st.selectbox("번지", user_df.columns, index=user_df.columns.get_loc('번지') if '번지' in user_df.columns else 0)
            with c3: col_year = st.selectbox("건축년도", user_df.columns, index=user_df.columns.get_loc('건축년도') if '건축년도' in user_df.columns else 0)
            with c4: col_area = st.selectbox("계약면적", user_df.columns, index=user_df.columns.get_loc('계약면적(㎡)') if '계약면적(㎡)' in user_df.columns else 0)

            if st.button("🚀 정밀 역추적 시작"):
                results = []
                my_bar = st.progress(0)
                
                for i, row in user_df.iterrows():
                    target_road = str(row[col_road]).strip()
                    blind_jibun = str(row[col_jibun]).strip()
                    target_year = str(row[col_year]).strip()
                    target_area = float(row[col_area]) if pd.notnull(row[col_area]) else 0
                    
                    # 1단계: 도로명 필터링
                    candidates = master_db[master_db['newPlatPlc'].str.contains(target_road, na=False)]
                    
                    if not candidates.empty:
                        # 2단계: 번지 앞자리 필터링 (예: 8**)
                        first_digit = blind_jibun[0] if blind_jibun and blind_jibun[0].isdigit() else ""
                        if first_digit:
                            candidates = candidates[candidates['platPlc'].str.contains(f" {first_digit}", na=False)]
                        
                        # 3단계: 건축년도 대조 (±1년 허용)
                        if target_year and target_year != 'nan':
                            y_val = int(target_year)
                            matched_year = candidates[candidates['대장연도'].isin([str(y_val-1), str(y_val), str(y_val+1)])]
                            if not matched_year.empty:
                                candidates = matched_year

                        # 4단계: [지능형 면적 대조] 
                        if target_area > 0 and not candidates.empty:
                            # 후보들 중 연면적이나 건축면적이 계약면적과 비슷한 게 있는지 확인 (±3% 오차)
                            # 만약 계약면적이 건물 연면적과 비슷하다면 '통건물 거래'로 간주하여 강력 필터링
                            matched_area = candidates[
                                ((candidates['totArea'] * 0.97 <= target_area) & (target_area <= candidates['totArea'] * 1.03)) |
                                ((candidates['archArea'] * 0.97 <= target_area) & (target_area <= candidates['archArea'] * 1.03))
                            ]
                            
                            # 면적이 일치하는 건물이 있다면 그것만 남김 (통거래 가능성)
                            # 일치하는 게 없다면 '호실 거래'로 보고 후보군 전체를 유지 (삭제하지 않음)
                            if not matched_area.empty:
                                candidates = matched_area

                        found_list = candidates['platPlc'].unique().tolist()
                        clean_list = [str(j).split()[-1] for j in found_list]
                        
                        res = row.to_dict()
                        res['추적_유력지번'] = ", ".join(clean_list[:3]) # 유력 후보 최대 3개
                        res['후보수'] = len(clean_list)
                        res['신뢰도'] = '⭐⭐⭐' if len(clean_list) <= 2 else '⭐'
                        results.append(res)
                    else:
                        res = row.to_dict()
                        res['추적_유력지번'] = '데이터없음'
                        results.append(res)
                    
                    my_bar.progress((i + 1) / len(user_df))

                result_df = pd.DataFrame(results)
                st.success("🎉 역추적 완료!")
                st.dataframe(result_df)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    result_df.to_excel(writer, index=False)
                st.download_button("📥 결과 다운로드", output.getvalue(), "원탑_역추적_결과.xlsx")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")