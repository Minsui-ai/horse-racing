import streamlit as st
import pandas as pd
import plotly.express as px
import os
from pathlib import Path
from datetime import datetime

# --- 1. 경로 및 설정 ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
if not OUTPUT_DIR.exists():
    os.makedirs(OUTPUT_DIR)

st.set_page_config(page_title="Racing Data Intelligence", layout="wide")

# --- 2. 데이터 보정 핵심 함수 (계산식 포함) ---
def calibrate_market_share(df):
    """
    네이버의 상대지수(Ratio)를 실제 점유율(Share)로 변환하는 핵심 로직
    계산식: (연령별 Ratio * 인구 가중치) / (전체 연령대 조정점수 합) * 100
    """
    if df.empty:
        return df
    
    # 분석에서 'Total' 행은 제외하고 개별 연령대만 추출
    # 네이버 연령 코드: 3(20대), 4(30대), 5(40대), 6(50대)
    cal_df = df[df['age_group'] != 'Total'].copy()
    
    # [인구 가중치 설정] 
    # 실제 검색을 수행하는 모집단의 크기를 반영 (대한민국 인구 통계 비율 예시)
    weights = {
        '3': 0.18,  # 20대
        '4': 0.22,  # 30대
        '5': 0.25,  # 40대
        '6': 0.35   # 50대 이상 (경마 시장의 주요 타겟)
    }
    
    # Step 1: 각 로우에 가중치 적용 (조정 점수 산출)
    cal_df['adj_score'] = cal_df.apply(
        lambda x: x['ratio'] * weights.get(str(x['age_group']), 0.1), axis=1
    )
    
    # Step 2: 날짜별로 조정 점수의 합계 계산 (그날의 전체 검색 볼륨 추정)
    cal_df['daily_total_vol'] = cal_df.groupby('date')['adj_score'].transform('sum')
    
    # Step 3: 최종 점유율(%) 계산
    # 특정 날짜에 모든 연령대의 share_percent를 더하면 100%가 됨
    cal_df['share_percent'] = (cal_df['adj_score'] / cal_df['daily_total_vol']) * 100
    
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

# --- 4. 메인 대시보드 UI ---
st.title("🏇 Racing Market Intelligence Dashboard")
st.markdown("네이버 트렌드 지수를 **인구 비중 대비 점유율**로 보정한 리포트입니다.")

raw_df = load_data()

if raw_df.empty:
    st.warning("데이터 파일이 없습니다. `collector.py`를 실행하거나 `outputs` 폴더에 CSV를 넣어주세요.")
else:
    # 데이터 보정 실행
    display_df = calibrate_market_share(raw_df)
    
    # 사이드바 필터
    with st.sidebar:
        st.header("🔍 필터 설정")
        target_kw = st.selectbox("분석 키워드", options=display_df['keyword'].unique())
        selected_df = display_df[display_df['keyword'] == target_kw]

    # 화면 구성
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📅 '{target_kw}' 연령대별 검색 점유율 추이")
        # 누적 영역 차트: 시간에 따른 점유율 변화를 100% 기준으로 시각화
        fig = px.area(selected_df, x="date", y="share_percent", color="age_group",
                      line_group="age_group", labels={'share_percent': '점유율 (%)'},
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("📊 평균 시장 점유율")
        avg_share = selected_df.groupby("age_group")["share_percent"].mean().reset_index()
        fig_pie = px.pie(avg_share, values='share_percent', names='age_group', 
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 5. 계산식 투명성 공개 (주석 및 수식) ---
    with st.expander("📝 데이터 보정 계산식 및 로직 안내", expanded=True):
        st.markdown(f"""
        ### 1. 보정의 목적
        네이버 API가 제공하는 `Ratio`는 각 연령대 내에서의 상대값일 뿐, 전체 시장에서의 **절대적 비중**을 나타내지 않습니다. 
        본 대시보드는 이를 해결하기 위해 인구 통계 가중치를 적용하여 **시장 점유율(Share)**을 산출합니다.

        ### 2. 적용 수식
        특정 날짜($t$)의 연령대($a$)에 대한 점유율($Share_{a,t}$)은 다음과 같이 계산됩니다:
        
        $$Share_{a,t} = \\frac{Ratio_{a,t} \\times Weight_a}{\\sum_{i \\in Ages} (Ratio_{i,t} \\times Weight_i)} \\times 100$$

        * **$Ratio_{a,t}$**: 네이버 API가 제공한 연령대별 검색 지수
        * **$Weight_a$**: 해당 연령대의 실제 인구 비중 (20대: 0.18, 30대: 0.22, 40대: 0.25, 50대: 0.35)
        """)
