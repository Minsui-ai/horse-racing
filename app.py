import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- 1. 환경 설정 ---
load_dotenv()
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver API Debugger", layout="wide")

# --- 2. API 호출 함수 ---
@st.cache_data(ttl=3600)
def call_naver_api(url, method="GET", body=None):
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API Key가 누락되었습니다.")
        return None
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    request.add_header("Content-Type", "application/json")
    try:
        response = urllib.request.urlopen(request, data=json.dumps(body).encode("utf-8") if body else None)
        return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        st.error(f"API 호출 오류: {e}")
        return None

def fetch_search_trends(keywords, start_date, end_date, selected_ages):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
        "ages": selected_ages
    }
    return call_naver_api(url, method="POST", body=body)

# --- 3. 데이터 가공 및 오류 추적 로직 ---
def process_trend_data_with_debug(data):
    if not data or "results" not in data: 
        return pd.DataFrame(), "데이터가 비어있거나 형식이 잘못되었습니다."
    
    rows = []
    # 인구 가중치 및 매핑
    weights = {'3': 0.18, '4': 0.22, '5': 0.25, '6': 0.35}
    age_map = {'1':'10대 미만','2':'10대','3':'20대','4':'30대','5':'40대','6':'50대','7':'60대 이상'}
    
    for result in data["results"]:
        kw = result["title"]
        if not result["data"]:
            rows.append({"키워드": kw, "상태": "데이터 없음(누락)"})
            continue

        for entry in result["data"]:
            raw_age = entry.get("age")
            ratio = entry.get("ratio", 0)
            status = "정상"
            
            # [1] Age 값 존재 여부 및 타입 체크
            if raw_age is None:
                age_code = "Unknown"
                status = "Age값 누락"
            else:
                try:
                    # '3.0' 또는 3 등의 다양한 입력을 문자열 '3'으로 통일
                    age_code = str(int(float(raw_age)))
                except:
                    age_code = str(raw_age)
                    status = f"타입변환실패({raw_age})"

            # [2] 매핑 및 가중치 계산
            age_name = age_map.get(age_code, f"기타(코드:{age_code})")
            if age_name.startswith("기타") and status == "정상":
                status = "매핑테이블에 없는 코드"
                
            weight = weights.get(age_code, 0.1)
            adj_score = ratio * weight
            
            rows.append({
                "날짜": entry.get("period"),
                "키워드": kw,
                "연령대": age_name,
                "연령대코드": age_code,
                "검색지수": ratio,
                "조정점수": adj_score,
                "상태": status
            })
    
    df = pd.DataFrame(rows)
    if not df.empty and "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"])
        # 정상 데이터만 계산에 참여
        valid_mask = df["조정점수"].notnull()
        df.loc[valid_mask, 'daily_total'] = df[valid_mask].groupby(['날짜', '키워드'])['조정점수'].transform('sum')
        df['점유율'] = (df['조정점수'] / df['daily_total']) * 100
        
    return df, "성공"

# --- 4. 메인 UI ---
with st.sidebar:
    st.title("🔧 시스템 제어판")
    if st.button("🔥 캐시 강제 삭제 및 초기화"):
        st.cache_data.clear()
        st.rerun()

    input_keywords = st.text_input("분석 키워드", "선풍기, 제습기")
    keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]
    
    date_range = st.date_input("분석 기간", [datetime.now() - timedelta(days=30), datetime.now()])
    
    st.write("**분석 연령대**")
    age_options = {"20대": "3", "30대": "4", "40대": "5", "50대": "6"}
    selected_labels = st.multiselect("대상", options=list(age_options.keys()), default=list(age_options.keys()))
    target_ages = [age_options[label] for label in selected_labels]

# --- 5. 결과 출력 ---
if len(date_range) == 2:
    start_date, end_date = date_range
    trend_raw = fetch_search_trends(keywords, start_date, end_date, target_ages)
    trend_df, msg = process_trend_data_with_debug(trend_raw)

    if not trend_df.empty:
        tab1, tab2 = st.tabs(["📈 분석 차트", "🕵️ 데이터 디버깅"])

        with tab1:
            sel_kw = st.selectbox("키워드 선택", options=trend_df['키워드'].unique())
            plot_df = trend_df[(trend_df['키워드'] == sel_kw) & (trend_df['상태'] == "정상")]
            
            if not plot_df.empty:
                fig = px.area(plot_df, x="날짜", y="점유율", color="연령대", title=f"'{sel_kw}' 보정 점유율 추이")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("차트를 그릴 수 있는 '정상' 상태의 데이터가 없습니다.")

        with tab2:
            st.subheader("🕵️ 원본 데이터 상태 분석")
            st.write("모든 행의 처리 상태를 확인합니다. '기타'로 나온다면 아래 테이블의 **연령대코드**와 **상태**를 확인하세요.")
            
            # 상태별 필터링 기능
            status_filter = st.multiselect("상태별 보기", options=trend_df['상태'].unique(), default=trend_df['상태'].unique())
            st.dataframe(trend_df[trend_df['상태'].isin(status_filter)], use_container_width=True)
            
            st.info("""
            **주요 오류 원인 가이드:**
            1. **Age값 누락**: 네이버가 해당 날짜/키워드에 대한 연령 정보를 제공하지 않음 (검색량 미달).
            2. **매핑테이블에 없는 코드**: 선택한 연령대 외의 코드가 들어옴 (예: 7, 8 등).
            3. **타입변환실패**: API 응답 값이 숫자가 아닌 특수문자나 예상치 못한 형식을 포함함.
            """)
    else:
        st.error(f"데이터를 처리할 수 없습니다. (메시지: {msg})")
