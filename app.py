import streamlit as st
import pandas as pd
import plotly.express as px
import os
from pathlib import Path
from datetime import datetime

# --- 1. 경로 및 설정 ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

st.set_page_config(page_title="Racing Data Intelligence", layout="wide")

# --- 2. 데이터 보정 핵심 함수 (점유율 계산) ---
def calibrate_market_share(df):
    if df.empty: return df
    
    # 분석에서 'Total' 행은 제외하고 개별 연령대만 추출
    cal_df = df[df['age_group'] != 'Total'].copy()
    
    # 인구 가중치 (국내 인구 비중 예시)
    weights = {'3': 0.18, '4': 0.22, '5': 0.25, '6': 0.35}
    
    # 가중치 적용 및 날짜별 점유율(%) 산출
    cal_df['adj_score'] = cal_df.apply(lambda x: x['ratio'] * weights.get(str(x['age_group']), 0.1), axis=1)
    cal_df['daily_total'] = cal_df.groupby(['date', 'keyword'])['adj_score'].transform('sum')
    cal_df['share_percent'] = (cal_df['adj_score'] / cal_df['daily_total']) * 100
    
    return cal_df

# --- 3. 데이터 로드 로직 ---
@st.cache_data
def load_data():
    trend_path = OUTPUT_DIR / "racing_trends_age.csv"
    if not trend_path.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(trend_path)
    df['date'] = pd.to_datetime(df['date'])
    return df

# --- 4. 메인 대시보드 및 사이드바 필터 ---
st.title("🏇 Racing Market Intel Dashboard")

raw_df = load_data()

if raw_df.empty:
    st.warning("데이터 파일이 없습니다. `outputs/racing_trends_age.csv` 파일을 확인해 주세요.")
else:
    # 데이터 보정 실행
    calibrated_df = calibrate_market_share(raw_df)
    
    # [사이드바 필터 영역]
    with st.sidebar:
        st.header("📊 분석 필터링")
        
        # 1. 키워드 선택
        all_keywords = calibrated_df['keyword'].unique()
        target_kw = st.selectbox("분석 키워드", options=all_keywords)
        
        # 2. 날짜 범위 선택
        min_date = calibrated_df['date'].min().to_pydatetime()
        max_date = calibrated_df['date'].max().to_pydatetime()
        date_range = st.date_input("분석 기간", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        
        # 3. 연령대 다중 선택
        all_ages = sorted(calibrated_df['age_group'].unique())
        selected_ages = st.multiselect("연령대 필터", options=all_ages, default=all_ages)
        
        st.divider()
        st.caption(f"최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # --- 5. 데이터 필터링 적용 ---
    # 날짜 범위 체크 (사용자가 범위를 다 선택했을 때만 실행)
    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (
            (calibrated_df['keyword'] == target_kw) &
            (calibrated_df['date'].dt.date >= start_date) &
            (calibrated_df['date'].dt.date <= end_date) &
            (calibrated_df['age_group'].isin(selected_ages))
        )
        filtered_df = calibrated_df[mask].sort_values('date')
    else:
        filtered_df = pd.DataFrame()

    # --- 6. 시각화 렌더링 ---
    if not filtered_df.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"📈 '{target_kw}' 점유율 추이")
            fig = px.area(filtered_df, x="date", y="share_percent", color="age_group",
                          labels={'share_percent': '점유율 (%)'},
                          color_discrete_sequence=px.colors.qualitative.Pastel,
                          template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("🥧 평균 점유율 비중")
            avg_share = filtered_df.groupby("age_group")["share_percent"].mean().reset_index()
            fig_pie = px.pie(avg_share, values='share_percent', names='age_group', 
                             hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        # 데이터 테이블 보기
        with st.expander("📄 상세 데이터 확인"):
            st.dataframe(filtered_df[['date', 'keyword', 'age_group', 'ratio', 'share_percent']])
    else:
        st.info("선택하신 조건에 맞는 데이터가 없습니다. 필터를 조정해 보세요.")

    # --- 7. 보정 공식 안내 (Raw String 사용) ---
    st.divider()
    with st.expander("📝 점유율 산출 공식 안내", expanded=False):
        st.markdown(r"""
        본 대시보드는 네이버 API의 상대 지수를 실제 시장 비중으로 환산하기 위해 아래 수식을 사용합니다.
        
        $$Share_{a,t} = \frac{Ratio_{a,t} \times Weight_a}{\sum (Ratio_{i,t} \times Weight_i)} \times 100$$
        """)
