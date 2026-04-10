import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# --- 1. 환경 설정 및 API 키 로드 ---
load_dotenv()

# Streamlit Secrets 혹은 환경 변수에서 로드
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver Market Intel Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- 2. API 호출 함수 (연령대 파라미터 추가) ---
@st.cache_data(ttl=3600)
def call_naver_api(url, method="GET", body=None):
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API Key가 설정되지 않았습니다. .env 혹은 Secrets를 확인해주세요.")
        return None
        
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    request.add_header("Content-Type", "application/json")
    
    try:
        if body:
            response = urllib.request.urlopen(request, data=json.dumps(body).encode("utf-8"))
        else:
            response = urllib.request.urlopen(request)
        
        if response.getcode() == 200:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

def fetch_search_trends(keywords, start_date, end_date, selected_ages):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
        "ages": selected_ages  # 연령대 필터 추가
    }
    return call_naver_api(url, method="POST", body=body)

def fetch_search_results(query, domain, display=100):
    url = f"https://openapi.naver.com/v1/search/{domain}.json?query={urllib.parse.quote(query)}&display={display}&sort=sim"
    return call_naver_api(url)

# --- 3. 데이터 가공 및 보정 로직 ---
def process_trend_data(data):
    if not data or "results" not in data:
        return pd.DataFrame()
        
    rows = []
    # [인구 가중치] 20대(3), 30대(4), 40대(5), 50대(6)
    weights = {'3': 0.18, '4': 0.22, '5': 0.25, '6': 0.35}
    
    for result in data["results"]:
        kw = result["title"]
        for entry in result["data"]:
            # API는 선택된 연령대별로 데이터를 줌
            age_code = entry.get("age", "Unknown")
            ratio = entry["ratio"]
            
            # 가중치 적용 (조정 점수 계산)
            adj_score = ratio * weights.get(age_code, 0.1)
            
            rows.append({
                "날짜": entry["period"], 
                "키워드": kw, 
                "연령대코드": age_code,
                "검색지수": ratio,
                "조정점수": adj_score
            })
            
    df = pd.DataFrame(rows)
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"])
        # 연령대 코드 매핑
        age_map = {'3': '20대', '4': '30대', '5': '40대', '6': '50대'}
        df["연령대"] = df["연령대코드"].map(age_map).fillna("기타")
        
        # 날짜/키워드별 전체 점수 합계를 구해 점유율(%) 산출
        df['daily_total'] = df.groupby(['날짜', '키워드'])['조정점수'].transform('sum')
        df['점유율'] = (df['조정점수'] / df['daily_total']) * 100
        
    return df

def process_search_results(all_results):
    rows = []
    for kw, domains in all_results.items():
        for d_name, data in domains.items():
            if data and "items" in data:
                for item in data["items"]:
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                    rows.append({
                        "키워드": kw, "구분": d_name, "제목": title, "설명": desc,
                        "링크": item.get("link", ""), "최저가": item.get("lprice", "0"),
                        "브랜드": item.get("brand", ""), "몰이름": item.get("mallName", ""),
                        "카테고리1": item.get("category1", ""), "카테고리2": item.get("category2", ""),
                        "카테고리3": item.get("category3", "")
                    })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["최저가"] = pd.to_numeric(df["최저가"], errors="coerce").fillna(0)
    return df

def get_word_freq(df, text_col):
    if df.empty or text_col not in df.columns: return pd.DataFrame()
    text = " ".join(df[text_col].astype(str))
    text = re.sub(r'[^\w\s]', '', text)
    words = [w for w in text.split() if len(w) > 1]
    freq = pd.Series(words).value_counts().head(30).reset_index()
    freq.columns = ["단어", "빈도"]
    return freq

# --- 4. 메인 UI (사이드바 필터 포함) ---
with st.sidebar:
    st.header("🔍 분석 컨트롤 타워")
    input_keywords = st.text_input("분석 키워드 (쉼표 구분)", "선풍기, 핫팩")
    keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]
    
    date_range = st.date_input("분석 기간", [datetime.now() - timedelta(days=90), datetime.now()])
    
    st.write("**연령대 설정 (보정용)**")
    age_options = {"20대": "3", "30대": "4", "40대": "5", "50대": "6"}
    selected_labels = st.multiselect("분석 연령대", options=list(age_options.keys()), default=list(age_options.keys()))
    target_ages = [age_options[label] for label in selected_labels]
    
    if st.button("실시간 데이터 분석 시작 🔄", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 데이터 수집 실행
@st.cache_data
def get_all_data(kws, s_date, e_date, ages):
    if len(date_range) != 2: return pd.DataFrame(), pd.DataFrame()
    
    with st.spinner('데이터를 수집 및 보정 중입니다...'):
        trend_raw = fetch_search_trends(kws, s_date, e_date, ages)
        trend_df = process_trend_data(trend_raw)
        
        search_data = {}
        domains = {"blog": "blog", "cafe": "cafearticle", "news": "news", "shop": "shop"}
        for kw in kws:
            search_data[kw] = {d_l: fetch_search_results(kw, d_a) for d_l, d_a in domains.items()}
        
        search_df = process_search_results(search_data)
        return trend_df, search_df

if len(date_range) == 2:
    start_date, end_date = date_range
    trend_df, search_df = get_all_data(keywords, start_date, end_date, target_ages)
else:
    trend_df, search_df = pd.DataFrame(), pd.DataFrame()

# --- 5. 탭 구성 및 시각화 ---
if trend_df.empty and search_df.empty:
    st.warning("수집된 데이터가 없습니다. 사이드바 설정을 확인해 주세요.")
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📉 프로파일링", "📊 점유율 분석", "🛍️ 쇼핑 상세", "💬 소셜 인사이트", "📂 데이터 탐색"])

    with tab1:
        st.subheader("📋 데이터 수집 현황")
        m1, m2, m3 = st.columns(3)
        m1.metric("트렌드 레코드", f"{len(trend_df)}건")
        m2.metric("검색 결과 수", f"{len(search_df)}건")
        m3.metric("최종 업데이트", datetime.now().strftime("%H:%M:%S"))
        st.dataframe(trend_df.head(10).astype(str))

    with tab2:
        st.subheader("📊 인구 가중치 보정 연령대별 점유율")
        if not trend_df.empty:
            # 키워드별로 필터링하여 보여주기
            sel_kw = st.selectbox("분석할 키워드 선택", options=trend_df['키워드'].unique())
            plot_df = trend_df[trend_df['키워드'] == sel_kw]
            
            fig_share = px.area(plot_df, x="날짜", y="점유율", color="연령대",
                                title=f"'{sel_kw}' 연령대별 시장 점유율 추이 (합계 100%)",
                                labels={'점유율': '보정 점유율 (%)'},
                                color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_share, use_container_width=True)
            
            # 산출 근거 안내
            st.info("💡 네이버 지수에 실제 연령별 인구 비중을 가중치로 곱하여 산출한 데이터입니다.")
            with st.expander("📝 점유율 산출 공식 확인"):
                st.markdown(r"""
                $$Share_{a,t} = \frac{Ratio_{a,t} \times Weight_a}{\sum (Ratio_{i,t} \times Weight_i)} \times 100$$
                """)
        else:
            st.warning("트렌드 데이터가 부족합니다.")

    # (이하 tab3, tab4, tab5는 기존 코드의 구조를 그대로 유지하여 사용하시면 됩니다)
    with tab3:
        st.subheader("🛍️ 쇼핑 채널 분석")
        shop_df = search_df[search_df["구분"] == "shop"]
        if not shop_df.empty:
            fig_box = px.box(shop_df, x="키워드", y="최저가", color="키워드", title="상품 가격 분포")
            st.plotly_chart(fig_box, use_container_width=True)
            st.dataframe(shop_df.head(20))

    with tab4:
        st.subheader("💬 소셜 키워드 빈도")
        social_df = search_df[search_df["구분"].isin(["blog", "cafe", "news"])]
        if not social_df.empty:
            freq_df = get_word_freq(social_df, "제목")
            fig_freq = px.bar(freq_df, x="빈도", y="단어", orientation="h", title="핵심 단어 Top 30")
            st.plotly_chart(fig_freq, use_container_width=True)

    with tab5:
        st.subheader("📂 raw 데이터 다운로드")
        st.dataframe(trend_df if st.checkbox("트렌드 데이터 보기") else search_df)
        csv = (trend_df if st.checkbox("트렌드 CSV") else search_df).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📁 데이터 다운로드", data=csv, file_name="naver_data.csv")
