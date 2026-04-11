import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import urllib.request
from datetime import datetime, timedelta
import os

# --- 1. 페이지 설정 및 밝은 테마 커스텀 CSS ---
st.set_page_config(page_title="Naver DataLab Insight", layout="wide", page_icon="📈")

st.markdown("""
<style>
    /* 전체 배경 및 기본 텍스트 설정 (Bright Theme) */
    .stApp { background-color: #fcfcfc; color: #333333; }
    
    /* 헤더 및 제목 스타일 */
    .main-header { font-size: 2.2rem; font-weight: 800; color: #2ecc71; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #666666; margin-bottom: 2rem; }
    
    /* 리포트 카드 디자인 */
    .report-card { 
        background-color: #ffffff; border-radius: 12px; padding: 25px; 
        box-shadow: 0 2px 15px rgba(0,0,0,0.08);
        border: 1px solid #eeeeee; margin-bottom: 20px;
        color: #333333;
    }
    
    /* 탭 스타일링 */
    .stTabs [data-baseweb="tab"] { color: #888888; font-weight: 500; }
    .stTabs [aria-selected="true"] { color: #2ecc71 !important; border-bottom-color: #2ecc71 !important; }
</style>
""", unsafe_allow_html=True)

# API 인증 정보 (Streamlit Secrets 혹은 환경변수)
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

# --- 2. 네이버 API 엔진 클래스 ---
class NaverInformer:
    def __init__(self, c_id, c_secret):
        self.c_id = c_id
        self.c_secret = c_secret

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
            st.error(f"API 호출 중 오류 발생: {e}")
            return None

# --- 3. 사이드바 제어판 ---
with st.sidebar:
    st.header("⚙️ 분석 설정")
    input_kw = st.text_input("분석 키워드 (쉼표 구분)", "핫팩, 선풍기, 가습기")
    keywords = [k.strip() for k in input_kw.split(",") if k.strip()]
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", datetime.now() - timedelta(days=90))
    end_date = col2.date_input("종료일", datetime.now())
    
    gender_choice = st.selectbox("성별 필터", ["전체", "남성", "여성"])
    gender_code = {"전체": None, "남성": "m", "여성": "f"}[gender_choice]
    
    st.divider()
    run_btn = st.button("🚀 통합 분석 시작", use_container_width=True)

# --- 4. 메인 분석 엔진 및 UI ---
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API 인증 정보가 설정되지 않았습니다. Secrets를 확인하세요.")
        st.stop()

    api = NaverInformer(CLIENT_ID, CLIENT_SECRET)
    st.markdown(f'<p class="main-header">Market Analysis Insight</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-header">{", ".join(keywords)} 에 대한 데이터 요약입니다.</p>', unsafe_allow_html=True)

    with st.spinner("네이버 빅데이터 분석 중..."):
        # 데이터 수집 1: 시계열 트렌드 (선택 필터 적용)
        trend_res = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), gender=gender_code)
        
        # 데이터 수집 2: 연령대별 전수 조사 (루프)
        age_map = {"10대": "1", "20대": "3", "30대": "5", "40대": "7", "50대": "9", "60대+": "11"}
        age_results = []
        for label, code in age_map.items():
            res = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), ages=[code], gender=gender_code)
            if res:
                for r in res['results']:
                    df_tmp = pd.DataFrame(r['data'])
                    if not df_tmp.empty:
                        age_results.append({"Keyword": r['title'], "AgeGroup": label, "AvgRatio": df_tmp['ratio'].mean()})
        df_age = pd.DataFrame(age_results)

    # --- 탭 구성 시작 ---
    tab_trend, tab_age, tab_summary = st.tabs(["📈 기간별 트렌드", "🥧 연령별 비중", "📋 경향 요약"])

    # [Tab 1: 기간별 트렌드]
    with tab_trend:
        st.subheader("일별 검색 지수 변화")
        if trend_res:
            trend_data_list = []
            for r in trend_res['results']:
                tdf = pd.DataFrame(r['data'])
                tdf['keyword'] = r['title']
                trend_data_list.append(tdf)
            
            df_full_trend = pd.concat(trend_data_list)
            df_full_trend['period'] = pd.to_datetime(df_full_trend['period'])
            
            fig_line = px.line(df_full_trend, x='period', y='ratio', color='keyword',
                               template="plotly_white", line_shape="spline",
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_line.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.warning("데이터가 존재하지 않습니다.")

    # [Tab 2: 연령별 비중]
    with tab_age:
        st.subheader("세그먼트별 관심도 분석")
        if not df_age.empty:
            for kw in keywords:
                kw_age_df = df_age[df_age['Keyword'] == kw]
                st.markdown(f"#### 🔍 {kw} 연령대 분석")
                col_p, col_t = st.columns([1.5, 1])
                with col_p:
                    fig_pie = px.pie(kw_age_df, values='AvgRatio', names='AgeGroup', hole=0.5,
                                     template="plotly_white", 
                                     color_discrete_sequence=px.colors.sequential.Teal)
                    fig_pie.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#ffffff', width=2)))
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_t:
                    st.write("**연령별 점수 순위**")
                    st.table(kw_age_df.sort_values(by='AvgRatio', ascending=False).reset_index(drop=True))
        else:
            st.warning("연령별 데이터를 수집하지 못했습니다.")

    # [Tab 3: 경향 요약]
    with tab_summary:
        st.subheader("인사이트 리포트")
        for kw in keywords:
            kw_t = df_full_trend[df_full_trend['keyword'] == kw]
            kw_a = df_age[df_age['Keyword'] == kw]
            
            with st.container():
                st.markdown(f'<div class="report-card">', unsafe_allow_html=True)
                st.markdown(f"### 📍 {kw}")
                
                c1, c2, c3 = st.columns(3)
                
                # 핵심 지표
                max_row = kw_t.loc[kw_t['ratio'].idxmax()]
                top_group = kw_a.loc[kw_a['AvgRatio'].idxmax(), 'AgeGroup']
                volatility = kw_t['ratio'].std()
                
                c1.metric("최고점 일자", max_row['period'].strftime('%Y-%m-%d'), f"{max_row['ratio']}pt")
                c2.metric("주력 타겟층", top_group)
                c3.metric("트렌드 안정성", "안정적" if volatility < 15 else "유동적", f"{volatility:.2f}")
                
                st.markdown(f"**💡 최종 분석:** {kw} 키워드는 **{top_group}** 세대에서 가장 활발한 검색이 발생하며, "
                            f"데이터상 **{max_row['period'].strftime('%m월 %d일')}**에 가장 높은 시장 민감도를 보였습니다.")
                st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("왼쪽 사이드바에서 키워드와 기간을 설정한 후 '통합 분석 시작' 버튼을 클릭해 주세요.")
