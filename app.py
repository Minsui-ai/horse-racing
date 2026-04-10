import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# --- 1. 환경 설정 및 API 키 확인 ---
# Streamlit Secrets 또는 .env에서 키를 가져옵니다.
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver Data Intelligence", layout="wide")

# --- 2. API 호출 함수 정의 ---
@st.cache_data(ttl=3600)
def fetch_search_trends(keywords, start_date, end_date, selected_ages):
    if not CLIENT_ID or not CLIENT_SECRET:
        return None
        
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
        "ages": selected_ages
    }
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    request.add_header("Content-Type", "application/json")
    
    try:
        response = urllib.request.urlopen(request, data=json.dumps(body).encode("utf-8"))
        return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

# --- 3. 데이터 가공 함수 ---
def process_trend_safe(data):
    if not data or "results" not in data:
        return pd.DataFrame(), "API 응답 데이터가 없거나 형식이 잘못되었습니다."
    
    rows = []
    age_map = {
        '1':'0-12세', '2':'13-18세', '3':'19-24세', '4':'25-29세', 
        '5':'30-34세', '6':'35-39세', '7':'40-44세', '8':'45-49세', 
        '9':'50-54세', '10':'55-59세', '11':'60세 이상'
    }
    # 인구 가중치 (기존 로직 유지)
    weights = {'3': 0.18, '4': 0.22, '5': 0.25, '6': 0.35}

    for result in data["results"]:
        kw = result["title"]
        if not result.get("data"): continue

        for entry in result["data"]:
            raw_age = entry.get("age", "Unknown")
            try:
                age_code = str(int(float(raw_age)))
            except:
                age_code = str(raw_age)
            
            ratio = entry.get("ratio", 0)
            age_name = age_map.get(age_code, f"미분류({age_code})")
            
            rows.append({
                "날짜": entry.get("period"),
                "키워드": kw,
                "연령대": age_name,
                "연령대코드": age_code,
                "검색지수": ratio,
                "조정점수": ratio * weights.get(age_code, 0.1)
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, "조건에 맞는 데이터가 없습니다. (검색량 부족)"
    
    df["날짜"] = pd.to_datetime(df["날짜"])
    df['daily_total'] = df.groupby(['날짜', '키워드'])['조정점수'].transform('sum')
    df['점유율'] = (df['조정점수'] / df['daily_total']) * 100
    return df, "성공"

# --- 4. 메인 UI 및 실행 로직 ---
st.sidebar.title("🔍 검색 설정")
input_kw = st.sidebar.text_input("키워드 (쉼표 구분)", "선풍기, 제습기")
keywords = [k.strip() for k in input_kw.split(",") if k.strip()]

date_range = st.sidebar.date_input("분석 기간", [datetime.now() - timedelta(days=30), datetime.now()])

age_opts = {'19-24세':'3', '25-29세':'4', '30-34세':'5', '35-39세':'6', '40-44세':'7', '45-49세':'8'}
selected_labels = st.sidebar.multiselect("분석 연령대", options=list(age_opts.keys()), default=list(age_opts.keys()))
target_ages = [age_opts[l] for l in selected_labels]

if st.sidebar.button("데이터 분석 실행"):
    if not keywords:
        st.warning("키워드를 입력해주세요.")
    elif len(date_range) < 2:
        st.warning("시작일과 종료일을 모두 선택해주세요.")
    else:
        with st.spinner('네이버 데이터를 불러오는 중...'):
            # [해결 포인트] trend_raw 변수를 여기서 정의합니다.
            trend_raw = fetch_search_trends(keywords, date_range[0], date_range[1], target_ages)
            
            if trend_raw:
                df, msg = process_trend_safe(trend_raw)
                
                if not df.empty:
                    st.success("데이터 분석 완료")
                    tab1, tab2 = st.tabs(["📉 점유율 차트", "📋 원본 데이터"])
                    
                    with tab1:
                        sel_kw = st.selectbox("분석 키워드 선택", options=df['키워드'].unique())
                        fig = px.area(df[df['키워드'] == sel_kw], x="날짜", y="점유율", color="연령대", 
                                      title=f"'{sel_kw}' 연령대별 보정 점유율 (%)")
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with tab2:
                        st.dataframe(df)
                else:
                    st.error(f"데이터 처리 실패: {msg}")
            else:
                st.error("API로부터 데이터를 받지 못했습니다. API 키와 네트워크를 확인하세요.")
