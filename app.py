import streamlit as st
import pandas as pd
import plotly.express as px
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# --- 1. UI 설정 ---
st.set_page_config(page_title="Custom Market Intel", layout="wide")

st.markdown("""
<style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- 2. API 설정 ---
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    st.error("🔑 **API Key 누락**: Streamlit Secrets에 ID와 Secret을 설정해주세요.")
    st.stop()

# 연령대 코드 매핑
AGE_MAP = {
    "10대": ["1", "2"],
    "20대": ["3", "4"],
    "30대": ["5", "6"],
    "40대": ["7", "8"],
    "50대": ["9", "10"],
    "60대+": ["11"]
}

# --- 3. 유틸리티 함수 ---
def fetch_naver_datalab(keyword, start_date, end_date, selected_ages):
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # 기본 그룹: 전체 (기준점용)
    keyword_groups = [{"groupName": "전체", "keywords": [keyword]}]
    
    # 선택된 연령대 추가 (최대 4개까지 추가 가능, 전체 포함 총 5개 제한)
    for age_label in selected_ages[:4]:
        keyword_groups.append({
            "groupName": age_label,
            "keywords": [keyword],
            "ages": AGE_MAP[age_label]
        })

    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": keyword_groups
    }

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    req.add_header("Content-Type", "application/json")

    try:
        response = urllib.request.urlopen(req, data=json.dumps(body).encode("utf-8"))
        res_code = response.getcode()
        if res_code == 200:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
    return None

# --- 4. 사이드바 컨트롤러 ---
with st.sidebar:
    st.header("🔍 분석 설정")
    
    # 키워드 입력
    user_keyword = st.text_input("분석할 키워드를 입력하세요", value="경마")
    
    # 기간 설정
    today = datetime.now()
    d_range = st.date_input("분석 기간 (최대 90일 권장)", 
                            [today - timedelta(days=30), today])
    
    # 연령대 선택 (최대 4개까지만 선택하도록 안내)
    all_ages = list(AGE_MAP.keys())
    selected_ages = st.multiselect("비교할 연령대 선택 (최대 4개)", 
                                   options=all_ages, default=["20대", "40대"])
    
    if len(selected_ages) > 4:
        st.warning("⚠️ 네이버 API 제한으로 '전체' 제외 최대 4개 연령대만 동시 비교 가능합니다.")

    st.divider()
    run_button = st.button("🚀 데이터 분석 실행")

# --- 5. 메인 대시보드 ---
st.title(f"📊 '{user_keyword}' 시장 분석 리포트")

if run_button:
    if len(d_range) != 2:
        st.warning("시작일과 종료일을 모두 선택해주세요.")
    else:
        start_date, end_date = d_range
        with st.spinner("네이버 빅데이터를 정규화하여 수집 중..."):
            data = fetch_naver_datalab(user_keyword, start_date, end_date, selected_ages)
            
            if data:
                # 데이터 정제
                rows = []
                for result in data['results']:
                    group_name = result['title']
                    for entry in result['data']:
                        rows.append({
                            "날짜": entry['period'],
                            "연령대": group_name,
                            "검색량(지수)": entry['ratio']
                        })
                
                df = pd.DataFrame(rows)
                df['날짜'] = pd.to_datetime(df['날짜'])

                # 시각화 1: 트렌드 라인 차트
                st.subheader("💡 검색 트렌드 통합 비교 (정규화 완료)")
                fig_line = px.line(df, x="날짜", y="검색량(지수)", color="연령대",
                                   line_shape="spline", template="plotly_white",
                                   color_discrete_map={"전체": "#334155"})
                fig_line.update_traces(patch={"line": {"width": 4}}, selector={"name": "전체"})
                st.plotly_chart(fig_line, use_container_width=True)

                # 시각화 2: 연령대별 평균 점유율 (전체 제외)
                col1, col2 = st.columns([1, 1])
                age_only_df = df[df['연령대'] != '전체']
                
                with col1:
                    st.write("### 🥧 연령대별 검색 비중 (평균)")
                    avg_df = age_only_df.groupby("연령대")["검색량(지수)"].mean().reset_index()
                    fig_pie = px.pie(avg_df, values="검색량(지수)", names="연령대", 
                                     hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with col2:
                    st.write("### 📈 기간 내 최대치 요약")
                    max_df = df.groupby("연령대")["검색량(지수)"].max().reset_index()
                    st.table(max_df)
                
                st.success(f"데이터 수집 완료: {start_date} ~ {end_date}")
            else:
                st.error("데이터를 가져오지 못했습니다. 키워드나 API 설정을 확인하세요.")
else:
    st.info("왼쪽 사이드바에서 조건을 설정한 후 **[데이터 분석 실행]** 버튼을 눌러주세요.")
