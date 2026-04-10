import streamlit as st
import pandas as pd
import plotly.express as px
import json
import urllib.request
from datetime import datetime, timedelta

# --- 1. UI 및 페이지 설정 ---
st.set_page_config(page_title="Racing Market Intelligence", layout="wide")

st.markdown("""
<style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; background-color: #2563eb; color: white; }
    .main { background-color: #f8fafc; }
</style>
""", unsafe_allow_html=True)

# --- 2. API 인증 설정 ---
# Streamlit Secrets 또는 직접 입력 (테스트용)
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

if CLIENT_ID == "YOUR_CLIENT_ID":
    st.sidebar.warning("⚠️ Secrets에 NAVER API 키를 설정하거나 코드의 ID/Secret을 수정하세요.")

# --- 3. 핵심 데이터 수집 및 계산 함수 ---
def get_normalized_data(keyword, start_date, end_date):
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # [중요] '전체'를 포함하여 5개 그룹을 한 번에 요청 (기준점 통합)
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [
            {"groupName": "전체", "keywords": [keyword]},
            {"groupName": "20대", "keywords": [keyword], "ages": ["3", "4"]},
            {"groupName": "30대", "keywords": [keyword], "ages": ["5", "6"]},
            {"groupName": "40대", "keywords": [keyword], "ages": ["7", "8"]},
            {"groupName": "50대", "keywords": [keyword], "ages": ["9", "10"]}
        ]
    }

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    req.add_header("Content-Type", "application/json")

    try:
        response = urllib.request.urlopen(req, data=json.dumps(body).encode("utf-8"))
        res_code = response.getcode()
        if res_code == 200:
            data = json.loads(response.read().decode("utf-8"))
            
            # 데이터프레임 변환
            rows = []
            for result in data['results']:
                group_name = result['title']
                for entry in result['data']:
                    rows.append({
                        "date": entry['period'],
                        "age_group": group_name,
                        "ratio": entry['ratio']
                    })
            
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])
            
            # --- 실질 비중(%) 재계산 로직 ---
            # 각 날짜별 '전체' 지수를 분모로 사용하여 연령별 점유율 계산
            total_df = df[df['age_group'] == '전체'].set_index('date')['ratio']
            
            def calculate_share(row):
                total_val = total_df.get(row['date'], 0)
                if total_val > 0:
                    return (row['ratio'] / total_val) * 100
                return 0
            
            df['share'] = df.apply(calculate_share, axis=1)
            return df
            
    except Exception as e:
        st.error(f"데이터 수집 중 오류: {e}")
    return None

# --- 4. 사이드바 컨트롤러 ---
with st.sidebar:
    st.header("🔍 분석 설정")
    target_kw = st.text_input("분석 키워드", value="경마")
    
    today = datetime.now()
    d_range = st.date_input("분석 기간", [today - timedelta(days=30), today])
    
    st.divider()
    run_btn = st.button("🚀 시장 데이터 분석")
    st.caption("네이버 데이터랩 API를 통해 실시간 정규화 분석을 수행합니다.")

# --- 5. 메인 대시보드 레이아웃 ---
st.title("🏇 Racing Market Intel Dashboard")

if run_btn:
    if len(d_range) == 2:
        start_date, end_date = d_range
        with st.spinner("네이버 빅데이터 분석 중..."):
            df = get_normalized_data(target_kw, start_date, end_date)
            
            if df is not None and not df.empty:
                # '전체' 데이터를 제외한 순수 연령대 비교 데이터
                age_only_df = df[df['age_group'] != '전체']
                
                # 상단 지표
                avg_share = age_only_df.groupby("age_group")["share"].mean()
                top_age = avg_share.idxmax()
                
                cols = st.columns(3)
                cols[0].metric("주요 타겟층", top_age)
                cols[1].metric(f"{top_age} 평균 점유율", f"{avg_share.max():.1f}%")
                cols[2].metric("분석 기간", f"{(end_date - start_date).days}일")

                # 시각화 1: 시계열 점유율 변화 (Area Chart)
                st.subheader(f"📈 '{target_kw}' 연령대별 검색 점유율 추이 (%)")
                fig_area = px.area(age_only_df, x="date", y="share", color="age_group",
                                   line_shape="spline", template="plotly_white",
                                   labels={"share": "점유율 (%)", "date": "날짜"},
                                   color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_area, use_container_width=True)

                # 시각화 2: 평균 비중 및 데이터 요약
                col_left, col_right = st.columns([1, 1])
                
                with col_left:
                    st.write("### 🥧 평균 마켓 쉐어")
                    fig_pie = px.pie(age_only_df.groupby("age_group")["share"].mean().reset_index(), 
                                     values="share", names="age_group", hole=0.4,
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with col_right:
                    st.write("### 📋 연령별 요약 통계")
                    summary = age_only_df.groupby("age_group")["share"].agg(['mean', 'max', 'min']).reset_index()
                    summary.columns = ['연령대', '평균 비중(%)', '최대 비중(%)', '최소 비중(%)']
                    st.dataframe(summary.style.highlight_max(axis=0, color='#e2e8f0'), use_container_width=True)

                st.info(f"💡 **분석 결과:** {target_kw} 키워드는 기간 내 평균적으로 **{top_age}**에서 가장 높은 검색 비중을 보였습니다.")
            else:
                st.warning("데이터를 가져오지 못했습니다. 키워드를 확인해주세요.")
    else:
        st.error("시작일과 종료일을 모두 선택해주세요.")
else:
    st.info("왼쪽 사이드바에서 키워드와 기간을 설정한 후 **[시장 데이터 분석]** 버튼을 눌러주세요.")
