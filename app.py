import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import urllib.request
from datetime import datetime, timedelta
import os

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="DataLab Insight Dashboard", layout="wide", page_icon="📈")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .main-header { font-size: 2.2rem; font-weight: 800; color: #00c3ff; margin-bottom: 1rem; }
    .stat-card { 
        background-color: #1d2127; border-radius: 10px; padding: 20px; 
        border: 1px solid #30363d; height: 100%;
    }
</style>
""", unsafe_allow_html=True)

# API 인증 정보
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

# --- 2. API 엔진 클래스 ---
class NaverInformer:
    def __init__(self, c_id, c_secret):
        self.c_id, self.c_secret = c_id, c_secret

    def get_trend_data(self, kws, start, end, ages=None, gender=None):
        url = "https://openapi.naver.com/v1/datalab/search"
        body = {
            "startDate": start, "endDate": end, "timeUnit": "date",
            "keywordGroups": [{"groupName": k, "keywords": [k]} for k in kws]
        }
        if ages: body["ages"] = ages
        if gender: body["gender"] = gender
        
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", self.c_id)
        req.add_header("X-Naver-Client-Secret", self.c_secret)
        req.add_header("Content-Type", "application/json")
        
        try:
            res = urllib.request.urlopen(req, data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
            return json.loads(res.read().decode('utf-8'))
        except Exception as e:
            return None

# --- 3. 사이드바 제어판 ---
with st.sidebar:
    st.header("⚙️ 분석 설정")
    input_kw = st.text_input("분석 키워드 (쉼표 구분)", "핫팩, 선풍기, 캠핑")
    keywords = [k.strip() for k in input_kw.split(",") if k.strip()]
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", datetime.now() - timedelta(days=90))
    end_date = col2.date_input("종료일", datetime.now())
    
    gender_choice = st.selectbox("성별 필터", ["전체", "남성", "여성"])
    gender_code = {"전체": None, "남성": "m", "여성": "f"}[gender_choice]
    
    run_btn = st.button("🚀 데이터 분석 시작", use_container_width=True)

# --- 4. 메인 분석 엔진 ---
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API 인증 정보가 설정되지 않았습니다.")
        st.stop()

    api = NaverInformer(CLIENT_ID, CLIENT_SECRET)
    st.markdown(f'<p class="main-header">🔍 마켓 인사이트: {", ".join(keywords)}</p>', unsafe_allow_html=True)
    
    # 데이터 수집 (1. 시계열 트렌드용 / 2. 연령별 비중용)
    with st.spinner("네이버 데이터 수집 중..."):
        # A. 시계열 데이터 (선택한 조건)
        raw_trend = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), gender=gender_code)
        
        # B. 연령별 루프 데이터
        age_map = {"10대": "1", "20대": "3", "30대": "5", "40대": "7", "50대": "9", "60대+": "11"}
        age_results = []
        for label, code in age_map.items():
            res = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), ages=[code], gender=gender_code)
            if res:
                for r in res['results']:
                    df_t = pd.DataFrame(r['data'])
                    if not df_t.empty:
                        age_results.append({"Keyword": r['title'], "Age": label, "Ratio": df_t['ratio'].mean()})
        
        df_age = pd.DataFrame(age_results)

    # --- 탭 구성 ---
    tab1, tab2, tab3 = st.tabs(["📈 기간별 트렌드", "🥧 연령별 비중", "📋 분석 요약"])

    # [Tab 1: 기간별 트렌드]
    with tab1:
        st.subheader("일별 검색 지수 추이")
        trend_list = []
        if raw_trend:
            for r in raw_trend['results']:
                temp = pd.DataFrame(r['data'])
                temp['keyword'] = r['title']
                trend_list.append(temp)
            
            df_trend = pd.concat(trend_list)
            df_trend['period'] = pd.to_datetime(df_trend['period'])
            
            fig_line = px.line(df_trend, x='period', y='ratio', color='keyword',
                               template="plotly_dark", line_shape="spline",
                               labels={"ratio": "검색 상대 지수", "period": "날짜"})
            fig_line.update_layout(hovermode="x unified")
            st.plotly_chart(fig_line, use_container_width=True)
            
            st.info("💡 100점은 설정 기간 내 가장 검색량이 많았던 날을 의미합니다.")

    # [Tab 2: 연령별 비중]
    with tab2:
        st.subheader("세그먼트별 관심도 분포")
        for kw in keywords:
            kw_age_df = df_age[df_age['Keyword'] == kw]
            if not kw_age_df.empty:
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    fig_pie = px.pie(kw_age_df, values='Ratio', names='Age', hole=0.5,
                                     title=f"[{kw}] 연령별 관심 비중",
                                     color_discrete_sequence=px.colors.sequential.Blues_r)
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_b:
                    st.write(f"#### {kw} 연령별 순위")
                    st.table(kw_age_df.sort_values(by='Ratio', ascending=False).reset_index(drop=True))

    # [Tab 3: 분석 요약]
    with tab3:
        st.subheader("데이터 경향성 한눈에 보기")
        
        for kw in keywords:
            kw_trend = df_trend[df_trend['keyword'] == kw]
            kw_age = df_age[df_age['Keyword'] == kw]
            
            with st.container():
                st.markdown(f"### 📍 {kw} 리포트")
                c1, c2, c3 = st.columns(3)
                
                # 지표 1: 최고점 날짜
                max_row = kw_trend.loc[kw_trend['ratio'].idxmax()]
                c1.metric("최고점 도달일", max_row['period'].strftime('%Y-%m-%d'), f"{max_row['ratio']}pt")
                
                # 지표 2: 주력 타겟
                top_age = kw_age.loc[kw_age['Ratio'].idxmax(), 'Age']
                c2.metric("핵심 타겟층", top_age)
                
                # 지표 3: 변동성 (표준편차)
                volatility = kw_trend['ratio'].std()
                status = "급변동" if volatility > 20 else "안정적"
                c3.metric("트렌드 변동성", status, f"{volatility:.2f}")
                
                # 요약 설명
                st.write(f"**분석 의견:** {kw} 키워드는 {top_age}를 중심으로 {max_row['period'].strftime('%B')} 경에 가장 높은 관심을 보였습니다. 해당 기간 전후로 마케팅 집중이 필요합니다.")
                st.markdown("---")

else:
    st.info("분석하려는 키워드와 기간을 설정한 후 실행 버튼을 눌러주세요.")
