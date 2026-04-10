import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import urllib.request
from datetime import datetime, timedelta

# --- 1. 환경 설정 ---
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver Data Debugger", layout="wide")

# --- 2. 데이터 가공 함수 (방어적 설계) ---
def process_trend_safe(data):
    if not data or "results" not in data:
        return pd.DataFrame(), "API 응답에 결과가 없습니다."
    
    rows = []
    # 네이버 연령대 코드 전체 매핑 (1~11)
    age_map = {
        '1':'0-12세', '2':'13-18세', '3':'19-24세', '4':'25-29세', 
        '5':'30-34세', '6':'35-39세', '7':'40-44세', '8':'45-49세', 
        '9':'50-54세', '10':'55-59세', '11':'60세 이상'
    }
    # 가중치 (선택된 연령대 위주, 나머지는 기본값 0.1)
    weights = {'3': 0.18, '4': 0.22, '5': 0.25, '6': 0.35}

    for result in data["results"]:
        kw = result["title"]
        if not result.get("data"):
            continue # 이 키워드에 데이터가 없으면 패스

        for entry in result["data"]:
            # age가 숫자로 오든 문자로 오든 안전하게 처리
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
        return df, "조건에 맞는 데이터 포인트가 하나도 없습니다. (검색량 부족 가능성)"
    
    df["날짜"] = pd.to_datetime(df["날짜"])
    # 점유율 계산
    df['daily_total'] = df.groupby(['날짜', '키워드'])['조정점수'].transform('sum')
    df['점유율'] = (df['조정점수'] / df['daily_total']) * 100
    
    return df, "성공"

# --- 3. 메인 로직 ---
st.sidebar.title("🔍 검색 설정")
input_kw = st.sidebar.text_input("키워드", "선풍기")
kws = [k.strip() for k in input_kw.split(",")]

# 연령대 선택 (전체 선택 가능하게 변경)
age_opts = {'19-24세':'3', '25-29세':'4', '30-34세':'5', '35-39세':'6', '40-44세':'7', '45-49세':'8'}
selected_labels = st.sidebar.multiselect("분석 연령대", options=list(age_opts.keys()), default=list(age_opts.keys()))
target_ages = [age_opts[l] for l in selected_labels]

if st.sidebar.button("데이터 분석 실행"):
    # API 호출 부분 (기존 코드와 동일하되 결과만 process_trend_safe로 전달)
    # ... (API 호출 코드 생략) ...
    
    # 예시: API 결과가 trend_raw에 담겼다고 가정
    df, msg = process_trend_safe(trend_raw)
    
    if not df.empty:
        st.success(f"데이터 로드 성공! (상태: {msg})")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = px.line(df, x="날짜", y="점유율", color="연령대", title="연령대별 추이")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("📋 수집된 데이터 샘플")
            st.dataframe(df[['날짜', '연령대', '연령대코드', '검색지수']].head(10))
    else:
        st.error(f"오류 발생: {msg}")
        st.info("💡 팁: 키워드를 더 대중적인 단어로 바꾸거나, 기간을 늘려보세요. 네이버는 검색량이 적은 경우 세부 연령 데이터를 제공하지 않습니다.")
