import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import json
import urllib.request
import re
import io

# --- 1. 페이지 설정 및 스타일링 ---
st.set_page_config(page_title="네이버 마켓 인사이트", layout="wide", page_icon="📈")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .report-card { 
        background-color: #161b22; border-radius: 10px; padding: 20px; 
        border-left: 5px solid #00ff88; margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

# API 키 설정 (Streamlit Secrets 우선)
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

# --- 2. 네이버 API 엔진 ---
class NaverInformer:
    def __init__(self, c_id, c_secret):
        self.c_id = c_id
        self.c_secret = c_secret

    def _request(self, url, method='GET', body=None):
        try:
            req = urllib.request.Request(url)
            req.add_header("X-Naver-Client-Id", self.c_id)
            req.add_header("X-Naver-Client-Secret", self.c_secret)
            if method == 'POST':
                req.add_header("Content-Type", "application/json")
                response = urllib.request.urlopen(req, data=body.encode("utf-8"))
            else:
                response = urllib.request.urlopen(req)
            
            if response.getcode() == 200:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            st.error(f"API 통신 오류: {e}")
        return None

    def get_trend(self, kws, start, end, ages=None, gender=None):
        url = "https://openapi.naver.com/v1/datalab/search"
        body = {
            "startDate": start, "endDate": end, "timeUnit": "date",
            "keywordGroups": [{"groupName": k, "keywords": [k]} for k in kws]
        }
        if ages: body["ages"] = ages
        if gender: body["gender"] = gender
        return self._request(url, 'POST', json.dumps(body, ensure_ascii=False))

    def get_search(self, category, query):
        url = f"https://openapi.naver.com/v1/search/{category}.json?query={urllib.parse.quote(query)}&display=50"
        return self._request(url)

# --- 3. 사이드바 제어판 ---
with st.sidebar:
    st.title("🔍 분석 설정")
    input_kw = st.text_input("분석 키워드 (쉼표 구분)", "핫팩, 선풍기")
    keywords = [k.strip() for k in input_kw.split(",") if k.strip()]
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", datetime.now() - timedelta(days=90))
    end_date = col2.date_input("종료일", datetime.now())
    
    st.markdown("---")
    st.subheader("👥 타겟 세그먼트")
    age_map = {"10대": "1", "20대": "3", "30대": "5", "40대": "7", "50대": "9", "60대+": "11"}
    sel_ages = st.multiselect("연령대 (미선택 시 전체)", list(age_map.keys()))
    age_codes = [age_map[a] for a in sel_ages] if sel_ages else None
    
    gender_sel = st.radio("성별 필터", ["전체", "여성", "남성"], horizontal=True)
    gender_code = {"여성": "f", "남성": "m"}.get(gender_sel)
    
    run_btn = st.button("🚀 데이터 수집 시작", use_container_width=True)

# --- 4. 데이터 처리 및 시각화 ---
if run_btn:
    api = NaverInformer(CLIENT_ID, CLIENT_SECRET)
    
    with st.spinner("네이버 마켓 데이터를 분석 중입니다..."):
        # 트렌드 데이터 수집
        trend_res = api.get_trend(keywords, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), age_codes, gender_code)
        
        # 트렌드 데이터프레임 변환
        trend_list = []
        if trend_res and 'results' in trend_res:
            for res in trend_res['results']:
                temp_df = pd.DataFrame(res['data'])
                temp_df['keyword'] = res['title']
                trend_list.append(temp_df)
        
        if trend_list:
            df_t = pd.concat(trend_list)
            df_t['period'] = pd.to_datetime(df_t['period'])
            
            # 메인 대시보드 출력
            st.title("📈 마켓 인텔리전스 리포트")
            
            tab1, tab2, tab3 = st.tabs(["📊 트렌드 분석", "💬 소셜 여론", "📋 원본 데이터"])
            
            with tab1:
                st.subheader("키워드별 검색 점유율 추이")
                fig_line = px.line(df_t, x='period', y='ratio', color='keyword', 
                                   template="plotly_dark", title="시간 흐름에 따른 상대적 관심도")
                st.plotly_chart(fig_line, use_container_width=True)
                
                # 요약 지표
                avg_ratio = df_t.groupby('keyword')['ratio'].mean().reset_index()
                fig_bar = px.bar(avg_ratio, x='keyword', y='ratio', color='keyword', 
                                 template="plotly_dark", title="평균 시장 점유 비율")
                st.plotly_chart(fig_bar, use_container_width=True)

            with tab2:
                st.subheader("소셜/뉴스 토픽 분석")
                social_data = []
                for k in keywords:
                    res = api.get_search('blog', k)
                    if res and 'items' in res:
                        for item in res['items']:
                            social_data.append({
                                'keyword': k,
                                'title': re.sub('<[^>]*>', '', item['title']),
                                'description': re.sub('<[^>]*>', '', item['description'])
                            })
                
                df_s = pd.DataFrame(social_data)
                if not df_s.empty:
                    # 간단한 단어 빈도 시각화
                    all_titles = " ".join(df_s['title'])
                    words = [w for w in all_titles.split() if len(w) > 1]
                    word_counts = pd.Series(words).value_counts().head(20).reset_index()
                    word_counts.columns = ['단어', '빈도']
                    
                    fig_words = px.bar(word_counts, x='빈도', y='단어', orientation='h', 
                                       template="plotly_dark", color='빈도')
                    st.plotly_chart(fig_words, use_container_width=True)
                    
                    st.markdown('<div class="report-card"><strong>💡 분석가 코멘트:</strong> 현재 소셜 상에서는 키워드와 함께 위와 같은 단어들이 자주 언급되고 있습니다.</div>', unsafe_allow_html=True)

            with tab3:
                st.dataframe(df_t, use_container_width=True)
                csv = df_t.to_csv(index=False).encode('utf-8-sig')
                st.download_button("데이터 다운로드(CSV)", csv, "trend_data.csv", "text/csv")
        else:
            st.error("데이터를 불러오지 못했습니다. 키워드나 기간 설정을 확인해 주세요.")

else:
    st.info("👈 왼쪽 사이드바에서 조건을 설정하고 버튼을 눌러주세요.")
