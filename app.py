import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- 1. 환경 설정 및 API 키 로드 ---
load_dotenv()
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver Market Intel", layout="wide")

# --- 2. API 호출 함수 (연령대 파라미터 반영) ---
@st.cache_data(ttl=3600)
def call_naver_api(url, method="GET", body=None):
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API Key 설정 오류. .env 혹은 Secrets를 확인하세요.")
        return None
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    request.add_header("Content-Type", "application/json")
    try:
        response = urllib.request.urlopen(request, data=json.dumps(body).encode("utf-8") if body else None)
        if response.getcode() == 200:
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

def fetch_search_results(query, domain):
    url = f"https://openapi.naver.com/v1/search/{domain}.json?query={urllib.parse.quote(query)}&display=50&sort=sim"
    return call_naver_api(url)

# --- 3. 데이터 가공 및 '기타' 방지 로직 ---
def process_trend_data(data):
    if not data or "results" not in data: return pd.DataFrame()
    rows = []
    # 인구 가중치 (20대~50대 중심)
    weights = {'3': 0.18, '4': 0.22, '5': 0.25, '6': 0.35}
    
    for result in data["results"]:
        kw = result["title"]
        for entry in result["data"]:
            # 핵심: age를 무조건 문자열로 변환하여 딕셔너리 키와 일치시킴
            age_code = str(entry.get("age", "Unknown"))
            ratio = entry["ratio"]
            adj_score = ratio * weights.get(age_code, 0.1)
            
            rows.append({
                "날짜": entry["period"], "키워드": kw, "연령대코드": age_code,
                "검색지수": ratio, "조정점수": adj_score
            })
    
    df = pd.DataFrame(rows)
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"])
        # 매핑 딕셔너리 (문자열 키)
        age_map = {'1':'10대 미만','2':'10대','3':'20대','4':'30대','5':'40대','6':'50대','7':'60대 이상'}
        df["연령대"] = df["연령대코드"].map(age_map).fillna("기타")
        
        # 날짜/키워드별 점유율 계산
        df['daily_total'] = df.groupby(['날짜', '키워드'])['조정점수'].transform('sum')
        df['점유율'] = (df['조정점수'] / df['daily_total']) * 100
    return df

def process_search_results(all_results):
    rows = []
    for kw, domains in all_results.items():
        for d_name, data in domains.items():
            if data and "items" in data:
                for item in data["items"]:
                    rows.append({
                        "키워드": kw, "구분": d_name, 
                        "제목": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                        "최저가": pd.to_numeric(item.get("lprice", "0"), errors="coerce") or 0,
                        "브랜드": item.get("brand", ""), "링크": item.get("link", "")
                    })
    return pd.DataFrame(rows)

# --- 4. 메인 UI (사이드바 필터) ---
with st.sidebar:
    st.title("🔍 분석 설정")
    input_keywords = st.text_input("키워드 (쉼표 구분)", "선풍기, 핫팩")
    keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]
    
    date_range = st.date_input("분석 기간", [datetime.now() - timedelta(days=90), datetime.now()])
    
    st.write("**연령대 필터**")
    age_options = {"20대": "3", "30대": "4", "40대": "5", "50대": "6"}
    selected_labels = st.multiselect("분석 대상", options=list(age_options.keys()), default=list(age_options.keys()))
    target_ages = [age_options[label] for label in selected_labels]
    
    if st.button("데이터 분석 시작 🔄", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 5. 데이터 렌더링 ---
if len(date_range) == 2:
    start_date, end_date = date_range
    with st.spinner('데이터 수집 중...'):
        trend_raw = fetch_search_trends(keywords, start_date, end_date, target_ages)
        trend_df = process_trend_data(trend_raw)
        
        search_data = {}
        for kw in keywords:
            search_data[kw] = {d: fetch_search_results(kw, d_a) for d, d_a in {"blog":"blog", "shop":"shop", "news":"news"}.items()}
        search_df = process_search_results(search_data)

    if not trend_df.empty:
        tab1, tab2, tab3 = st.tabs(["📊 점유율 추이", "🛍️ 쇼핑 분석", "📂 원본 데이터"])
        
        with tab1:
            sel_kw = st.selectbox("키워드 선택", options=trend_df['키워드'].unique())
            fig = px.area(trend_df[trend_df['키워드'] == sel_kw], x="날짜", y="점유율", color="연령대",
                          title=f"'{sel_kw}' 연령대별 보정 점유율 (%)",
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
            st.info("💡 인구 가중치가 적용된 점유율입니다. '기타'로 나오면 캐시를 삭제해 주세요.")
            
        with tab2:
            if not search_df.empty:
                shop_df = search_df[search_df["구분"] == "shop"]
                fig_price = px.box(shop_df, x="키워드", y="최저가", color="키워드", title="상품 가격대 분포")
                st.plotly_chart(fig_price, use_container_width=True)
        
        with tab3:
            st.dataframe(trend_df)
            csv = trend_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 결과 다운로드", data=csv, file_name="market_intel.csv")
    else:
        st.warning("데이터를 불러오지 못했습니다. API 키와 키워드를 확인하세요.")
