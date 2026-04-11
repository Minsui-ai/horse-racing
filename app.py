import streamlit as st
import pandas as pd
import plotly.express as px
import json
import urllib.request
from datetime import datetime, timedelta
import os
import re

# --- 1. 페이지 설정 및 스타일링 ---
st.set_page_config(page_title="네이버 연령대별 마켓 분석", layout="wide", page_icon="🥧")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .report-card { 
        background-color: #1d2127; border-radius: 12px; padding: 25px; 
        border-top: 4px solid #00c3ff; margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# API 인증 정보 (Secrets 또는 환경변수)
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
        except: return None

# --- 3. 사이드바 제어판 ---
with st.sidebar:
    st.title("📊 분석 설정")
    input_kw = st.text_input("분석 키워드 (쉼표 구분)", "핫팩, 선풍기")
    keywords = [k.strip() for k in input_kw.split(",") if k.strip()]
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", datetime.now() - timedelta(days=90))
    end_date = col2.date_input("종료일", datetime.now())
    
    st.info("💡 연령대별 비중 분석은 모든 연령대 데이터를 순차적으로 호출하므로 키워드가 많을수록 시간이 소요될 수 있습니다.")
    run_btn = st.button("🚀 연령대 비중 분석 실행", use_container_width=True)

# --- 4. 메인 분석 로직 ---
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("API 인증 정보가 없습니다. 네이버 개발자 센터에서 발급받은 ID와 Secret을 설정해주세요.")
        st.stop()

    api = NaverInformer(CLIENT_ID, CLIENT_SECRET)
    age_map = {
        "10대": "1", "20대": "3", "30대": "5", 
        "40대": "7", "50대": "9", "60대+": "11"
    }

    # 데이터 수집 루프
    all_age_data = []
    
    progress_bar = st.progress(0)
    for i, (label, code) in enumerate(age_map.items()):
        status_text = f"🔄 {label} 데이터 수집 중..."
        st.write(status_text)
        
        res = api.get_trend_data(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), ages=[code])
        
        if res and 'results' in res:
            for r in res['results']:
                temp_df = pd.DataFrame(r['data'])
                if not temp_df.empty:
                    avg_val = temp_df['ratio'].mean()
                    all_age_data.append({
                        "Keyword": r['title'],
                        "AgeGroup": label,
                        "AverageRatio": avg_val
                    })
        progress_bar.progress((i + 1) / len(age_map))

    # 결과 데이터프레임 생성
    df_dist = pd.DataFrame(all_age_data)

    if not df_dist.empty:
        st.title("🥧 키워드별 연령대 마켓 비중")
        st.markdown("---")

        for kw in keywords:
            kw_df = df_dist[df_dist['Keyword'] == kw]
            
            with st.container():
                st.markdown(f'<div class="report-card"><h3>🔍 {kw} 분석 리포트</h3></div>', unsafe_allow_html=True)
                
                c1, c2 = st.columns([1.2, 1])
                
                with c1:
                    # 파이 차트 시각화
                    fig = px.pie(kw_df, values='AverageRatio', names='AgeGroup', hole=0.4,
                                 template="plotly_dark", 
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    fig.update_layout(showlegend=False, margin=dict(t=30, b=30, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.write("#### 🏆 타겟 순위")
                    # 데이터 정렬 및 표시
                    sorted_df = kw_df.sort_values(by='AverageRatio', ascending=False).reset_index(drop=True)
                    st.dataframe(sorted_df[['AgeGroup', 'AverageRatio']], 
                                 column_config={"AverageRatio": st.column_config.ProgressColumn("검색 지수 평균", format="%.2f", min_value=0, max_value=100)},
                                 use_container_width=True)
                    
                    top_group = sorted_df.iloc[0]['AgeGroup']
                    st.success(f"이 상품의 핵심 타겟은 **{top_group}** 세대입니다.")

        # 전체 데이터 다운로드
        st.markdown("---")
        csv = df_dist.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 분석 데이터 전체 다운로드 (CSV)", csv, "age_distribution.csv", "text/csv")
    else:
        st.error("데이터를 수집하지 못했습니다. 키워드나 날짜 범위를 다시 확인해주세요.")

else:
    # 대시보드 초기 화면
    st.info("👈 왼쪽 사이드바에서 키워드를 입력하고 '연령대 비중 분석 실행' 버튼을 눌러주세요.")
    st.markdown("""
    ### 📈 분석 가이드
    1. **다중 키워드:** 콤마(,)로 구분하여 여러 키워드를 동시에 분석할 수 있습니다.
    2. **데이터 호출:** 모든 연령대를 순차적으로 호출하여 검색 비중을 계산합니다.
    3. **활용:** 어느 연령대에서 가장 높은 반응을 보이는지 확인하여 광고 타겟팅 전략을 세울 수 있습니다.
    """)
