import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib.request
import json
import os
import re
import io
from sklearn.feature_extraction.text import TfidfVectorizer

# --- 1. 기본 환경 설정 및 유틸리티 ---
st.set_page_config(page_title="Naver Intelligence Dashboard", layout="wide", initial_sidebar_state="expanded")

# 프리미엄 디자인 CSS 적용 (Plotly는 기본적으로 한글을 잘 지원합니다)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background-color: #0e1117; color: #ffffff; }
    .analyst-insight { 
        background-color: #161b22; 
        border-radius: 10px; 
        padding: 20px; 
        border-left: 5px solid #ffcc00; 
        margin-top: 15px; 
        margin-bottom: 25px;
        font-size: 15px; 
        line-height: 1.8; 
        color: #e6edf3; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .data-card {
        background: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #3d4255;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 저장 이미지 및 데이터 디렉토리 설정
OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

TREND_FILE = os.path.join(OUTPUT_DIR, "market_trends_detailed.csv")
SEARCH_FILE = os.path.join(OUTPUT_DIR, "social_search_results.csv")

def save_and_display_chart(fig, caption, insight, stats_df=None):
    """차트를 화면에 출력하고 분석가 인사이트를 함께 표시"""
    # Plotly 다크 테마 적용
    fig.update_layout(template="plotly_dark", font_family="Outfit")
    st.plotly_chart(fig, use_container_width=True)
    
    if stats_df is not None:
        with st.expander(f"📊 {caption} 상세 통계 분석표"):
            st.dataframe(stats_df, use_container_width=True)
    
    st.markdown(f'<div class="analyst-insight"><strong>📢 분석가 심층 해석:</strong><br>{insight}</div>', unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 (Naver API) ---

def call_naver_api(url, body):
    try:
        # Streamlit Secrets 또는 환경 변수에서 키 로드
        client_id = st.secrets.get("NAVER_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
        client_secret = st.secrets.get("NAVER_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            st.error("🔑 API 키가 설정되지 않았습니다. (st.secrets 혹은 환경변수 확인)")
            return None
            
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", client_id)
        request.add_header("X-Naver-Client-Secret", client_secret)
        request.add_header("Content-Type", "application/json")
        
        response = urllib.request.urlopen(request, data=body.encode("utf-8") if body else None)
        if response.getcode() == 200:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        st.error(f"⚠️ API 에러: {e}")
    return None

def collect_data(kws, start, end, age_grps, genders):
    # Datalab Trend
    url = "https://openapi.naver.com/v1/datalab/search"
    age_map = {"10대": ["1", "2"], "20대": ["3", "4"], "30대": ["5", "6"], "40대": ["7", "8"], "50대": ["9", "10"], "60대+": ["11"]}
    gender_map = {"전체": None, "남성": "m", "여성": "f"}
    
    t_results = []
    total_steps = len(kws) * len(age_grps) * (len(genders) if genders else 1)
    progress = st.progress(0)
    step = 0

    for kw in kws:
        for ag in age_grps:
            age_codes = age_map.get(ag, [])
            for gen in (genders if genders else ["전체"]):
                gen_code = gender_map.get(gen)
                body = {
                    "startDate": start, "endDate": end, "timeUnit": "date",
                    "keywordGroups": [{"groupName": kw, "keywords": [kw]}],
                    "ages": age_codes, "gender": gen_code
                }
                data = call_naver_api(url, json.dumps(body))
                if data:
                    for res in data['results']:
                        for row in res['data']:
                            t_results.append({
                                'date': row['period'], 'keyword': kw, 'age_group': ag,
                                'gender': gen, 'ratio': row['ratio']
                            })
                step += 1
                progress.progress(step / total_steps)
    
    df_t = pd.DataFrame(t_results)
    if not df_t.empty:
        df_t.to_csv(TREND_FILE, index=False, encoding='utf-8-sig')

    # Social Search
    s_url = "https://openapi.naver.com/v1/search/webkr.json"
    s_results = []
    for kw in kws:
        res = call_naver_api(f"{s_url}?query={urllib.parse.quote(kw)}&display=100", None)
        if res:
            for itm in res['items']:
                domain = "blog" if "blog.naver.com" in itm['link'] else "cafe" if "cafe.naver.com" in itm['link'] else "news" if "news.naver.com" in itm['link'] else "other"
                s_results.append({
                    'keyword': kw, 'title': re.sub('<[^>]*>', '', itm['title']),
                    'description': re.sub('<[^>]*>', '', itm['description']),
                    'link': itm['link'], 'domain': domain, 'date': datetime.now().strftime("%Y-%m-%d")
                })
    df_s = pd.DataFrame(s_results)
    if not df_s.empty:
        df_s.to_csv(SEARCH_FILE, index=False, encoding='utf-8-sig')
    
    progress.empty()
    return df_t, df_s

@st.cache_data
def load_processed_data(file):
    if os.path.exists(file):
        df = pd.read_csv(file)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df.drop_duplicates()
    return pd.DataFrame()

# --- 3. 사이드바 컨트롤 ---
with st.sidebar:
    st.title("🛡️ 20yr Analyst Dash")
    st.markdown("---")
    kw_raw = st.text_input("분석 키워드 (콤마)", "강아지 사료, 강아지 영양제")
    keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
    col1, col2 = st.columns(2)
    s_date = col1.date_input("시작", datetime.now() - timedelta(days=90))
    e_date = col2.date_input("종료", datetime.now())
    
    ages = st.multiselect("연령대", ["10대", "20대", "30대", "40대", "50대", "60대+"], ["20대", "30대", "40대"])
    gens = st.multiselect("성별", ["전체", "남성", "여성"], ["전체"])
    
    if st.button("🚀 데이터 분석 업데이트", use_container_width=True):
        with st.spinner("네이버 API 실시간 수집 및 프로세싱 중..."):
            collect_data(keywords, s_date.strftime("%Y-%m-%d"), e_date.strftime("%Y-%m-%d"), ages, gens)
            st.cache_data.clear()
            st.rerun()

# --- 4. 메인 분석 화면 ---
st.title("📈 네이버 마켓 인텔리전스 심층 리포트")
st.caption(f"분석 대상: {', '.join(keywords)} | 기간: {s_date} ~ {e_date}")

df_t = load_processed_data(TREND_FILE)
df_s = load_processed_data(SEARCH_FILE)

if not df_t.empty:
    tab_eda, tab_trend, tab_segment, tab_social = st.tabs(["📋 데이터 품질 진단", "📊 마켓 트렌드", "👥 타겟 세그먼트", "💬 소셜 인사이트"])

    # --- TAB 1: EDA ---
    with tab_eda:
        st.header("📊 데이터 프로파일링")
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 레코드 수", f"{len(df_t)} 건")
        c2.metric("고유 날짜 수", f"{df_t['date'].nunique()} 일")
        c3.metric("중복/결측치 합계", f"{df_t.duplicated().sum() + df_t.isna().sum().sum()} 건")
        
        st.markdown("### ✅ 데이터 구조 상세")
        buffer = io.StringIO()
        df_t.info(buf=buffer)
        st.text(buffer.getvalue())
        
        st.dataframe(df_t.describe(include='all').T, use_container_width=True)

    # --- TAB 2: 마켓 트렌드 ---
    with tab_trend:
        # Chart 1: 일간 추이
        fig1 = px.line(df_t[df_t['gender']=='전체'], x='date', y='ratio', color='keyword', line_group='age_group', title="[G01] 일간 검색어 상대지수 추이")
        save_and_display_chart(fig1, "일간 추이", "시계열 분석 결과, 특정 시점에서의 급격한 스파이크는 계절적 요인 혹은 매스미디어의 노출과 밀접한 연관이 있는 것으로 판단됩니다.")

        # Chart 2: 월간 평균
        df_t['month'] = df_t['date'].dt.to_period('M').astype(str)
        m_pivot = df_t.groupby(['month', 'keyword'])['ratio'].mean().reset_index()
        fig2 = px.bar(m_pivot, x='month', y='ratio', color='keyword', barmode='group', title="[G02] 월별 키워드 평균 관심도")
        save_and_display_chart(fig2, "월간 평균", "월간 단위로 데이터를 집계했을 때 시장의 성장세가 더욱 뚜렷하게 관찰되며, 이는 마케팅 자원 투입의 적기를 판단하는 지표가 됩니다.")

    # --- TAB 3: 세그먼트 ---
    with tab_segment:
        # Chart 5: 연령별 비중
        age_dist = df_t.groupby('age_group')['ratio'].mean().reset_index()
        fig5 = px.pie(age_dist, values='ratio', names='age_group', hole=0.5, title="[G05] 연령대별 관심도 점유율")
        save_and_display_chart(fig5, "연령대 비중", "연령별 점유율을 통해 핵심 페르소나를 설정하고 캠페인을 고도화할 필요가 있습니다.")

        # Chart 7: 트리맵
        fig7 = px.treemap(df_t[df_t['gender']!='전체'], path=['keyword', 'age_group', 'gender'], values='ratio', color='ratio', title="[G07] 다차원 시장 구조")
        save_and_display_chart(fig7, "시장 구조", "가장 수익성이 높은 니치 세그먼트를 시각적으로 탐색하여 비즈니스 포트폴리오를 최적화할 수 있습니다.")

    # --- TAB 4: 소셜 인사이트 ---
    with tab_social:
        if not df_s.empty:
            def get_tfidf_top(texts, top_n=20):
                if not texts: return pd.DataFrame()
                vec = TfidfVectorizer(max_features=100)
                mtx = vec.fit_transform(texts)
                scores = mtx.sum(axis=0).A1
                names = vec.get_feature_names_out()
                return pd.DataFrame({'Word': names, 'Score': scores}).sort_values(by='Score', ascending=False).head(top_n)

            tf_df = get_tfidf_top((df_s['title'] + " " + df_s['description']).tolist())
            fig9 = px.bar(tf_df, x='Score', y='Word', orientation='h', title="[G09] TF-IDF 기반 소셜 핵심 관심사")
            save_and_display_chart(fig9, "소셜 관심 키워드", "단순 빈도가 아닌 TF-IDF를 적용한 결과는 소비자들이 정보를 탐색할 때 결정적으로 고려하는 속성을 나타냅니다.")
        else:
            st.warning("데이터를 먼저 수집해 주세요.")
else:
    st.info("👈 사이드바에서 분석 조건을 설정한 후 '데이터 분석 업데이트' 버튼을 클릭하세요.")
