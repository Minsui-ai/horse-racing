import streamlit as st
import pandas as pd
import plotly.express as px
import json
import urllib.request
from datetime import datetime, timedelta

# --- 1. API 인증 (Secrets에서 로드) ---
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver Trend Analyzer", layout="wide")

# --- 2. API 호출 함수 (ages 파라미터 강제 주입) ---
def fetch_age_data(keyword, start_date, end_date, selected_ages):
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # [핵심] ages가 비어있으면 응답에 age 필드가 안 옵니다. 
    # 최소 하나 이상의 코드가 들어가야 데이터가 분류되어 내려옵니다.
    if not selected_ages:
        selected_ages = ["3", "4", "5", "6", "7", "8"] # 20대~50대 기본값
        
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
        "ages": selected_ages
    }
    
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    req.add_header("Content-Type", "application/json")
    
    try:
        res = urllib.request.urlopen(req, data=json.dumps(body).encode("utf-8"))
        return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        return None

# --- 3. 데이터 파싱 함수 ---
def parse_age_results(data):
    if not data or "results" not in data:
        return pd.DataFrame()
    
    age_map = {
        '1':'0-12세', '2':'13-18세', '3':'19-24세', '4':'25-29세', 
        '5':'30-34세', '6':'35-39세', '7':'40-44세', '8':'45-49세', 
        '9':'50-54세', '10':'55-59세', '11':'60세 이상'
    }
    
    rows = []
    for result in data["results"]:
        for entry in result.get("data", []):
            # age 필드가 없을 경우를 대비한 안전장치
            raw_age = entry.get("age", "ALL")
            rows.append({
                "날짜": entry["period"],
                "연령대": age_map.get(str(raw_age), "전체합계"),
                "검색지수": entry["ratio"]
            })
    return pd.DataFrame(rows)

# --- 4. 메인 화면 ---
st.title("📊 네이버 연령별 검색 트렌드")

with st.sidebar:
    keyword = st.text_input("분석 키워드", "삼성전자")
    days = st.slider("조회 기간 (일)", 7, 90, 30)
    
    st.write("---")
    age_options = {"20대": ["3", "4"], "30대": ["5", "6"], "40대": ["7"], "50대": ["8"]}
    selected_age_groups = st.multiselect("대상 연령대", list(age_options.keys()), default=["20대", "30대"])
    
    # 선택된 그룹의 코드를 리스트로 합치기
    final_ages = []
    for group in selected_age_groups:
        final_ages.extend(age_options[group])

if st.button("트렌드 분석 시작"):
    end_dt = datetime.now() - timedelta(days=2)
    start_dt = end_dt - timedelta(days=days)
    
    raw_res = fetch_age_data(keyword, start_dt, end_dt, final_ages)
    df = parse_age_results(raw_res)
    
    if not df.empty:
        # 차트 출력
        fig = px.line(df, x="날짜", y="검색지수", color="연령대", title=f"'{keyword}' 연령대별 관심도")
        st.plotly_chart(fig, use_container_width=True)
        
        # 데이터 시트
        with st.expander("원본 데이터 확인"):
            st.dataframe(df)
    else:
        st.warning("데이터를 가져오지 못했습니다. API 권한 및 키워드를 확인하세요.")
