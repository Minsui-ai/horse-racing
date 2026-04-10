import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta

# --- 1. UI 및 스타일 설정 ---
st.set_page_config(page_title="Racing Market Intelligence", layout="wide", initial_sidebar_state="expanded")

# 프리미엄 디자인을 위한 Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    .main { background-color: #f8fafc; }
    .stMetric { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
    }
    h1, h2, h3 { color: #0f172a; font-weight: 600; }
    .stButton>button {
        background-image: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white; border-radius: 8px; border: none; padding: 10px 24px;
        font-weight: 600; transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. API 설정 및 유틸리티 ---
# Streamlit Secrets에서 키 정보 가져오기
try:
    CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except Exception:
    st.error("🔑 **API 키 누락**: Streamlit Settings 또는 secrets.toml에 `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET`을 설정해 주세요.")
    st.stop()

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 연령대 그룹 매핑 (사용자 요청: 20대~50대)
AGE_GROUPS = {
    "20대": ["3", "4"],
    "30대": ["5", "6"],
    "40대": ["7", "8"],
    "50대": ["9", "10"]
}

def call_naver_api(url, method="GET", body=None):
    """네이버 API 통합 호출 함수 (에러 처리 및 상세 메시지 포함)"""
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
            
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        st.error(f"❌ **API 응답 코드 {e.code}**: {err_msg}")
    except Exception as e:
        st.error(f"❌ **예외 발생**: {str(e)}")
    return None

def fetch_datalab_trends(keywords, start_date, end_date, ages=None):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords]
    }
    if ages:
        body["ages"] = ages
    return call_naver_api(url, method="POST", body=body)

def collect_all_data():
    """실시간 데이터 수집 프로세스 (트렌드 + 소셜)"""
    keywords = ["경마", "한국마사회", "경마결과", "경마예상", "대상경주"]
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=90)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    with st.status("📊 실시간 마켓 데이터 동기화 중...", expanded=True) as status:
        all_trend_data = []
        
        # 1. 통합 트렌드 수집
        st.write("📈 전체 검색 트렌드 수집...")
        res_total = fetch_datalab_trends(keywords, start_str, end_str)
        if res_total:
            for r in res_total['results']:
                for d in r['data']:
                    all_trend_data.append({"date": d['period'], "keyword": r['title'], "ratio": d['ratio'], "age_group": "전체"})
        
        # 2. 연령대별 그룹 수집 (20대~50대)
        for group_name, age_codes in AGE_GROUPS.items():
            st.write(f"👥 {group_name} 트렌드 분석...")
            res_age = fetch_datalab_trends(keywords, start_str, end_str, ages=age_codes)
            if res_age:
                for r in res_age['results']:
                    for d in r['data']:
                        all_trend_data.append({"date": d['period'], "keyword": r['title'], "ratio": d['ratio'], "age_group": group_name})
        
        if all_trend_data:
            pd.DataFrame(all_trend_data).to_csv(OUTPUT_DIR / "racing_trends_age.csv", index=False, encoding='utf-8-sig')
        
        # 3. 소셜 검색 데이터 수집
        st.write("💬 최신 소셜 인사이트 데이터 수집...")
        social_results = []
        for kw in keywords[:2]: # 주요 키워드만 수행
            for domain in ["news", "blog", "cafearticle"]:
                url = f"https://openapi.naver.com/v1/search/{domain}.json?query={urllib.parse.quote(kw)}&display=30&sort=sim"
                data = call_naver_api(url)
                if data and 'items' in data:
                    for item in data['items']:
                        social_results.append({
                            "keyword": kw,
                            "domain": domain.replace("article", ""),
                            "title": item['title'].replace("<b>", "").replace("</b>", ""),
                            "link": item['link'],
                            "description": item['description'].replace("<b>", "").replace("</b>", ""),
                            "date": item.get('postdate') or item.get('pubDate', '')
                        })
        
        if social_results:
            pd.DataFrame(social_results).to_csv(OUTPUT_DIR / "racing_search_results.csv", index=False, encoding='utf-8-sig')
            
        status.update(label="✅ 데이터 수집 완료!", state="complete")
        st.cache_data.clear()
        st.rerun()

# --- 3. 데이터 로드 로직 ---
@st.cache_data
def load_cached_data():
    trend_path = OUTPUT_DIR / "racing_trends_age.csv"
    search_path = OUTPUT_DIR / "racing_search_results.csv"
    
    if not trend_path.exists():
        return pd.DataFrame(), pd.DataFrame()
        
    try:
        df_t = pd.read_csv(trend_path, encoding='utf-8-sig')
        df_s = pd.read_csv(search_path, encoding='utf-8-sig')
        df_t['date'] = pd.to_datetime(df_t['date'])
        return df_t, df_s
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_trend, df_search = load_cached_data()

# --- 4. 대시보드 레이아웃 ---
st.title("🏇 Racing Market Intel Dashboard")
st.markdown("네이버 빅데이터 기반 실시간 경마 검색 패턴 및 소셜 인사이트")

# 사이드바
with st.sidebar:
    st.image("https://img.icons8.com/isometric/512/horse-back-view.png", width=100)
    st.header("⚙️ Dashboard Control")
    
    if st.button("🚀 실시간 데이터 동기화", help="네이버 API를 통해 최신 데이터를 수집합니다."):
        collect_all_data()

    st.divider()
    if not df_trend.empty:
        st.subheader("🎯 분석 필터")
        sel_keywords = st.multiselect("키워드 선택", options=df_trend['keyword'].unique(), default=df_trend['keyword'].unique()[:2])
        sel_ages = st.multiselect("연령대 선택", options=df_trend['age_group'].unique(), default=["전체", "20대", "40대"])
        st.info("💡 20대~50대 연령별 세분화 분석이 가능합니다.")
    else:
        st.warning("수집된 데이터가 없습니다. 상단의 동기화 버튼을 눌러주세요.")

# 메인 콘텐츠
if not df_trend.empty:
    tab1, tab2, tab3 = st.tabs(["📈 트렌드 심층 분석", "👥 연령대별 비교", "💬 실시간 소셜 피드"])
    
    with tab1:
        st.subheader("키워드별 검색량 추이 (전체)")
        # 필터링
        plot_df = df_trend[(df_trend['keyword'].isin(sel_keywords)) & (df_trend['age_group'] == '전체')]
        if not plot_df.empty:
            fig1 = px.line(plot_df, x='date', y='ratio', color='keyword', 
                           template="plotly_white", color_discrete_sequence=px.colors.qualitative.Prism,
                           labels={"ratio": "검색 관심도", "date": "날짜"})
            fig1.update_layout(hovermode="x unified")
            st.plotly_chart(fig1, use_container_width=True)
            
            st.markdown("#### **📊 주요 통계표**")
            stats = plot_df.groupby("keyword")['ratio'].agg(['mean', 'max', 'min']).reset_index()
            st.table(stats)
            st.caption("※ 최대 검색량 100을 기준으로 환산된 상대적 지수입니다.")
        
    with tab2:
        st.subheader("연령대별 마켓 관심도 비교")
        target_kw = st.selectbox("비교 대상 키워드", options=sel_keywords)
        age_plot_df = df_trend[(df_trend['keyword'] == target_kw) & (df_trend['age_group'].isin(sel_ages))]
        
        col1, col2 = st.columns([2, 1])
        with col1:
            fig2 = px.area(age_plot_df, x='date', y='ratio', color='age_group', 
                           title=f"'{target_kw}' 연령대별 관심도 점유 추이", template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)
            
        with col2:
            avg_age = age_plot_df.groupby("age_group")["ratio"].mean().reset_index()
            fig3 = px.pie(avg_age, values='ratio', names='age_group', hole=0.4,
                          title="연령대별 평균 관심도 비중", color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig3, use_container_width=True)

        st.info(f"**💡 분석 결과**: '{target_kw}'에 대해 {avg_age.sort_values(by='ratio', ascending=False).iloc[0]['age_group']}의 관심도가 가장 높은 것으로 나타납니다.")

    with tab3:
        st.subheader("최신 소셜 인사이트 (News/Blog/Cafe)")
        if not df_search.empty:
            s_keywords = st.multiselect("콘텐츠 키워드 필터", options=df_search['keyword'].unique(), default=df_search['keyword'].unique()[:1])
            f_search = df_search[df_search['keyword'].isin(s_keywords)]
            
            for _, row in f_search.head(30).iterrows():
                with st.expander(f"[{row['domain'].upper()}] {row['title']}"):
                    st.write(row['description'])
                    st.caption(f"발행일: {row['date']}")
                    st.markdown(f"[🔗 연결 링크]({row['link']})")
        else:
            st.write("소셜 데이터가 없습니다.")

else:
    st.info("오른쪽 사이드바의 **[🚀 실시간 데이터 동기화]** 버튼을 클릭하여 분석을 시작하세요.")
    st.image("https://img.icons8.com/fluency/512/combo-chart.png", width=200)

# 하단 푸터
st.sidebar.markdown("---")
st.sidebar.caption(f"Final Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.caption("Powered by Naver API & Streamlit")
