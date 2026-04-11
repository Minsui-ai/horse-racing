import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import urllib.request
from datetime import datetime, timedelta
import os

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="Naver DataLab Pro", layout="wide", page_icon="📈")

# 다크 모드 기반 커스텀 스타일
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .main-header { font-size: 2.2rem; font-weight: 800; color: #00c3ff; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #8b949e; margin-bottom: 2rem; }
    .report-card { 
        background-color: #1d2127; border-radius: 10px; padding: 20px; 
        border: 1px solid #30363d; margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# API 인증 정보 (Secrets 설정 필요)
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
        except:
            return None

# --- 3. 사이드바 제어판 ---
with st.sidebar:
    st.header("⚙️ 분석 설정")
    input_kw = st.text_input("분석 키워드 (쉼표 구분)", "핫팩, 선풍기")
    keywords = [k.strip() for k in input_kw.split(",") if k.strip()]
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", datetime.now() - timedelta(days=90))
    end_date = col2.date_input("종료일", datetime.now())
    
    gender_choice = st.selectbox("성별 필터", ["전체", "남성", "여성"])
    gender_code = {"전체": None, "남성": "m", "여성": "f"}[gender_choice]
    
    st.divider()
    run_btn = st.button("🚀 통합 분석 실행", use_container_width=True)

# --- 4. 메인 대시보드 로직 ---
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API 인증 정보가 누락되었습니다. (.streamlit/secrets.toml 확인)")
        st.stop()

    api = NaverInformer(CLIENT_ID, CLIENT_SECRET)
    
    st.markdown(f'<p class="main-header">Market Analysis Report</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-header">{", ".join(keywords)} 에 대한 심층 분석 결과입니다.</p>', unsafe_allow_html=True)

    # 데이터 수집 (시계열용 + 연령별 루프)
    with st.spinner("네이버 빅데이터 분석 중..."):
        # [데이터 1] 시계열 트렌드 (선택 성별 기준)
        trend_res = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), gender=gender_code)
        
        # [데이터 2] 연령별 루프 (비중 분석용)
        age_map = {"10대": "1", "20대": "3", "30대": "5", "40대": "7", "50대": "9", "60대+": "11"}
        age_data_list = []
        for label, code in age_map.items():
            res = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), ages=[code], gender=gender_code)
            if res:
                for r in res['results']:
                    df_tmp = pd.DataFrame(r['data'])
                    if not df_tmp.empty:
                        age_data_list.append({"Keyword": r['title'], "Age": label, "AvgRatio": df_tmp['ratio'].mean()})
        df_age_final = pd.DataFrame(age_data_list)

    # --- 탭 구성 ---
    tab_trend, tab_age, tab_summary = st.tabs(["📈 기간별 트렌드", "🥧 연령별 비중", "📋 경향 요약"])

    # [Tab 1: 기간별 트렌드]
    with tab_trend:
        st.subheader("일별 검색 지수 변화 (Time-series)")
        if trend_res:
            trend_dfs = []
            for r in trend_res['results']:
                tdf = pd.DataFrame(r['data'])
                tdf['keyword'] = r['title']
                trend_dfs.append(tdf)
            
            df_full_trend = pd.concat(trend_dfs)
            df_full_trend['period'] = pd.to_datetime(df_full_trend['period'])
            
            fig_line = px.line(df_full_trend, x='period', y='ratio', color='keyword',
                               template="plotly_dark", line_shape="spline",
                               labels={"ratio": "검색 지수", "period": "날짜"})
            fig_line.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.warning("트렌드 데이터를 가져오지 못했습니다.")

    # [Tab 2: 연령별 비중]
    with tab_age:
        st.subheader("세그먼트별 관심도 분포 (Demographics)")
        if not df_age_final.empty:
            for kw in keywords:
                kw_age = df_age_final[df_age_final['Keyword'] == kw]
                col_pie, col_table = st.columns([1.5, 1])
                with col_pie:
                    fig_pie = px.pie(kw_age, values='AvgRatio', names='Age', hole=0.4,
                                     title=f"'{kw}' 연령별 검색 비중",
                                     color_discrete_sequence=px.colors.sequential.RdBu)
                    fig_pie.update_traces(textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_table:
                    st.write(f"**{kw}** 연령별 데이터 점수")
                    st.table(kw_age.sort_values(by='AvgRatio', ascending=False).reset_index(drop=True))
        else:
            st.warning("연령별 데이터를 가져오지 못했습니다.")

    # [Tab 3: 경향 요약]
    with tab_summary:
        st.subheader("데이터 인사이트 요약")
        for kw in keywords:
            # 해당 키워드 데이터 필터링
            kw_t = df_full_trend[df_full_trend['keyword'] == kw]
            kw_a = df_age_final[df_age_final['Keyword'] == kw]
            
            with st.container():
                st.markdown(f'<div class="report-card">', unsafe_allow_html=True)
                st.markdown(f"#### 📍 {kw} 리포트")
                
                c1, c2, c3 = st.columns(3)
                
                # 최고점 분석
                max_point = kw_t.loc[kw_t['ratio'].idxmax()]
                c1.metric("최대 검색일", max_point['period'].strftime('%Y-%m-%d'), f"{max_point['ratio']}pt")
                
                # 주력 연령층
                top_age = kw_a.loc[kw_a['AvgRatio'].idxmax(), 'Age']
                c2.metric("핵심 타겟층", top_age)
                
                # 변동성 (표준편차)
                volatility = kw_t['ratio'].std()
                v_status = "높음 (유행성)" if volatility > 15 else "낮음 (안정적)"
                c3.metric("트렌드 변동성", v_status, f"SD: {volatility:.2f}")
                
                st.write(f"**인사이트:** {kw} 키워드는 {top_age} 세대에서 가장 높은 충성도를 보이며, "
                         f"{max_point['period'].strftime('%m월 %d일')}에 관심도가 절정에 달했습니다.")
                st.markdown('</div>', unsafe_allow_html=True)

else:
    # 초기 화면 안내
    st.info("👈 왼쪽 사이드바에서 키워드를 입력하고 분석 버튼을 눌러주세요.")
    
    col_guide1, col_guide2 = st.columns(2)
    with col_guide1:
        st.markdown("### 📈 트렌드 탭\n설정한 기간 동안 검색량의 변화 추이를 보여줍니다. 계절성이나 특정 이벤트의 영향을 파악하기 좋습니다.")
    with col_guide2:
        st.markdown("### 🥧 비중 탭\n모든 연령대 데이터를 전수 조사하여, 어느 연령대가 이 시장의 주류인지 파이 차트로 분석합니다.")
