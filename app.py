import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# UI 설정
st.set_page_config(page_title="Racing Data Intelligence", layout="wide", initial_sidebar_state="expanded")

# CSS 커스텀 스타일
st.markdown("""
<style>
    .main { background-color: #f0f2f6; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .sidebar .sidebar-content { background-image: linear-gradient(#2e7bcf,#2e7bcf); color: white; }
    h1, h2, h3 { color: #1e3d59; }
</style>
""", unsafe_allow_html=True)

st.title("🏇 Racing Market Intel Dashboard")
st.markdown("네이버 API 기반 경마 데이터 및 연령대별 트렌드 분석")

# 데이터 로드 함수
@st.cache_data
def load_data():
    trend_path = os.path.join(OUTPUT_DIR, "racing_trends_age.csv")
    search_path = os.path.join(OUTPUT_DIR, "racing_search_results.csv")
    
    trend_df = pd.read_csv(trend_path) if os.path.exists(trend_path) else pd.DataFrame()
    search_df = pd.read_csv(search_path) if os.path.exists(search_path) else pd.DataFrame()
    
    if not trend_df.empty:
        trend_df['date'] = pd.to_datetime(trend_df['date'])
        
    return trend_df, search_df

trend_df, search_df = load_data()

# 사이드바 설정
with st.sidebar:
    st.header("📊 분석 필터")
    
    if not trend_df.empty:
        available_keywords = trend_df['keyword'].unique().tolist()
        selected_keywords = st.multiselect("분석 키워드", options=available_keywords, default=available_keywords[:3])
        
        available_ages = trend_df['age_group'].unique().tolist()
        selected_ages = st.multiselect("연령대 필터", options=available_ages, default=["Total", "20-24", "30-34", "40-44", "50-54"])
    else:
        st.warning("데이터가 없습니다. 수집을 먼저 실행해 주세요.")
        if st.button("데이터 수집 실행 (collector.py)"):
            st.info("터미널에서 'python src/collector.py'를 실행해 주세요.")

st.divider()

if trend_df.empty:
    st.info("수집된 데이터가 없습니다. `src/collector.py`를 실행하여 데이터를 수집하세요.")
else:
    tab1, tab2, tab3, tab4 = st.tabs(["📈 트렌드 분석", "👥 연령대별 비교", "🗺️ 히트맵 분석", "💬 소셜 인사이트"])
    
    with tab1:
        st.subheader("검색어별 트렌드 (Total)")
        total_df = trend_df[(trend_df['age_group'] == 'Total') & (trend_df['keyword'].isin(selected_keywords))]
        
        if not total_df.empty:
            fig = px.line(total_df, x="date", y="ratio", color="keyword", 
                          title="일별 검색 클릭 트렌드", template="plotly_white", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("선택한 키워드에 대한 데이터가 없습니다.")

    with tab2:
        st.subheader("연령대별 검색 선호도 비교")
        # 특정 키워드 하나를 선택해서 연령별 비교
        target_kw = st.selectbox("비교할 키워드 선택", options=selected_keywords)
        
        age_compare_df = trend_df[(trend_df['keyword'] == target_kw) & (trend_df['age_group'].isin(selected_ages))]
        
        if not age_compare_df.empty:
            fig_age = px.line(age_compare_df, x="date", y="ratio", color="age_group", 
                               title=f"'{target_kw}' 키워드 연령대별 트렌드", template="plotly_white")
            st.plotly_chart(fig_age, use_container_width=True)
            
            # 평균 검색량 바 차트
            avg_age = age_compare_df.groupby("age_group")["ratio"].mean().reset_index().sort_values("ratio", ascending=False)
            fig_bar = px.bar(avg_age, x="age_group", y="ratio", color="age_group", 
                             title=f"'{target_kw}' 연령대별 평균 관심도", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.write("데이터가 없습니다.")

    with tab3:
        st.subheader("연령대 x 키워드 관심도 히트맵")
        # 히트맵을 위해 연령대별 평균 ratio 계산
        heatmap_data = trend_df[trend_df['age_group'] != 'Total'].groupby(["keyword", "age_group"])["ratio"].mean().unstack()
        
        fig_heat = px.imshow(heatmap_data, text_auto=True, color_continuous_scale='Viridis',
                             title="키워드별 연령대별 관심도 지수 (평균 Ratio)")
        st.plotly_chart(fig_heat, use_container_width=True)
        
        st.info("Ratio는 해당 기간 내 최대 검색량을 100으로 잡은 상대적인 수치입니다.")

    with tab4:
        st.subheader("최신 소셜 및 뉴스 콘텐츠")
        if not search_df.empty:
            domain_filter = st.multiselect("채널 선택", options=search_df['domain'].unique(), default=search_df['domain'].unique())
            filtered_search = search_df[search_df['domain'].isin(domain_filter) & search_df['keyword'].isin(selected_keywords)]
            
            for index, row in filtered_search.head(20).iterrows():
                with st.container():
                    st.markdown(f"**[{row['domain'].upper()}] {row['title']}** ({row['date']})")
                    st.write(row['description'])
                    st.markdown(f"[링크 바로가기]({row['link']})")
                    st.divider()
        else:
            st.write("소셜 검색 결과 데이터가 없습니다.")

# 하단 정보
st.sidebar.markdown("---")
st.sidebar.write(f"최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
