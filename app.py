import streamlit as st
import pandas as pd
import plotly.express as px
import os
from pathlib import Path
from datetime import datetime

# --- 1. 경로 및 초기 설정 ---
# 배포 환경(/mount/src)과 로컬 환경 모두에서 작동하도록 설정
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

if not OUTPUT_DIR.exists():
    os.makedirs(OUTPUT_DIR)

st.set_page_config(page_title="Racing Data Intelligence", layout="wide")

# --- 2. 데이터 보정 핵심 로직 (Market Share Calibration) ---
def calibrate_market_share(df):
    """
    네이버의 상대지수(Ratio)를 실제 시장 점유율(Share)로 변환합니다.
    로직: (지수 * 인구 가중치)를 구한 뒤, 해당 날짜의 전체 합으로 나누어 % 산출
    """
    if df.empty:
        return df
    
    # 'Total'(전체 합산 지수)은 비중 계산에서 제외하고 개별 연령대만 추출
    # 네이버 코드: 3(20대), 4(30대), 5(40대), 6(50대)
    cal_df = df[df['age_group'] != 'Total'].copy()
    
    # [인구 가중치] 실제 모집단 크기를 반영한 가중치 (국내 인구 비중 예시)
    weights = {
        '3': 0.18,  # 20대
        '4': 0.22,  # 30대
        '5': 0.25,  # 40대
        '6': 0.35   # 50대 이상
    }
    
    # Step 1: 가중치 적용 (조정 점수 계산)
    cal_df['adj_score'] = cal_df.apply(
        lambda x: x['ratio'] * weights.get(str(x['age_group']), 0.1), axis=1
    )
    
    # Step 2: 날짜별 전체 조정 점수 합계 구하기 (분모)
    cal_df['daily_total'] = cal_df.groupby('date')['adj_score'].transform('sum')
    
    # Step 3: 최종 점유율(%) 계산 (분자 / 분모)
    cal_df['share_percent'] = (cal_df['adj_score'] / cal_df['daily_total']) * 100
    
    return cal_df

# --- 3. 데이터 로드 함수 ---
@st.cache_data
def load_data():
    trend_path = OUTPUT_DIR / "racing_trends_age.csv"
    if not trend_path.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(trend_path)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"파일 로드 중 오류: {e}")
        return pd.DataFrame()

# --- 4. 메인 UI 구성 ---
st.title("🏇 Racing Market Intel Dashboard")
st.info("💡 네이버 트렌드 지수를 **인구 비중 가중치**를 적용해 실제 점유율로 보정한 리포트입니다.")

raw_df = load_data()

if raw_df.empty:
    st.warning("📊 분석할 데이터가 없습니다. `outputs` 폴더에 `racing_trends_age.csv` 파일이 있는지 확인해 주세요.")
else:
    # 보정 로직 실행
    display_df = calibrate_market_share(raw_df)
    
    # 사이드바 필터
    with st.sidebar:
        st.header("📊 분석 설정")
        all_keywords = display_df['keyword'].unique()
        target_kw = st.selectbox("키워드 선택", options=all_keywords)
        
        st.divider()
        st.write(f"최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 필터링된 데이터
    selected_df = display_df[display_df['keyword'] == target_kw].sort_values('date')

    # 메인 시각화 영역
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"📈 '{target_kw}' 연령대별 점유율 추이")
        # 누적 영역 차트로 전체 100% 중 비중 변화 시각화
        fig = px.area(selected_df, x="date", y="share_percent", color="age_group",
                      title="일별 시장 점유율 (합계 100%)",
                      labels={'share_percent': '점유율 (%)', 'age_group': '연령대'},
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥧 평균 점유율 분포")
        avg_share = selected_df.groupby("age_group")["share_percent"].mean().reset_index()
        fig_pie = px.pie(avg_share, values='share_percent', names='age_group', 
                         hole=0.4, title="기간 내 평균 비중")
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 5. 수식 및 로직 가이드 (Raw String 사용으로 에러 방지) ---
    st.divider()
    with st.expander("📝 데이터 보정 산출 근거 확인", expanded=True):
        st.markdown(r"""
        ### 왜 데이터를 보정했나요?
        네이버 API의 `Ratio`는 각 그룹 내에서의 상대적 수치일 뿐입니다. 예를 들어 20대의 100점과 50대의 100점은 실제 검색량(인원수)에서 큰 차이가 납니다. 
        이를 위해 **인구 가중치**를 도입하여 실제 시장 점유율에 가깝게 재계산했습니다.

        ### 적용 계산식
        특정 날짜($t$)의 연령대($a$) 점유율($Share_{a,t}$)은 다음과 같이 계산됩니다:

        $$Share_{a,t} = \frac{Ratio_{a,t} \times Weight_a}{\sum_{i \in Ages} (Ratio_{i,t} \times Weight_i)} \times 100$$

        * **$Ratio$**: 네이버 API 검색 지수
        * **$Weight$**: 연령별 인구 가중치 (20대: 0.18, 30대: 0.22, 40대: 0.25, 50대: 0.35)
        """)
