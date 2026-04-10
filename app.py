import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

# 경로 설정 (실행 환경 및 클라우드 대응)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

# 필요한 디렉토리 자동 생성
for d in [DATA_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# UI 설정
st.set_page_config(page_title="Racing Data Intelligence", layout="wide", initial_sidebar_state="expanded")

# CSS 커스텀 스타일
st.markdown("""
<style>
    .main { background-color: #f0f2f6; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .sidebar .sidebar-content { background-image: linear-gradient(#2e7bcf,#2e7bcf); color: white; }
    h1, h2, h3 { color: #1e3d59; }
</style>
""", unsafe_allow_html=True)

st.title("🏇 Racing Market Intel Dashboard")
st.markdown("네이버 API 기반 경마 데이터 및 연령대별 트렌드 분석")

# --- 네이버 API 수집 로직 통합 ---
AGE_MAP = {"1": "0-12", "2": "13-18", "3": "19-24", "4": "25-29", "5": "30-34", "6": "35-39", "7": "40-44", "8": "45-49", "9": "50-54", "10": "55-59", "11": "60+"}

def call_naver_api(url, method="GET", body=None):
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
        st.error(f"API 호출 오류: {e}")
    return None

def fetch_trends(keywords, start_date, end_date, ages=None):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": "date", "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords]}
    if ages: body["ages"] = ages
    return call_naver_api(url, method="POST", body=body)

def collect_realtime_data():
    with st.status("🚀 실시간 데이터 수집 중...", expanded=True) as status:
        keywords = ["경마", "한국마사회", "경마결과", "경마예상", "대상경주"]
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        all_data = []
        st.write("📊 검색 트렌드 수집 중...")
        # 전체 및 연령대별 루프 (단축 버전)
        for age_code, age_label in {**{"0": "Total"}, **AGE_MAP}.items():
            st.write(f"- {age_label} 데이터 가져오는 중...")
            ages = [age_code] if age_code != "0" else None
            res = fetch_trends(keywords, start_date, end_date, ages=ages)
            if res:
                for r in res['results']:
                    for e in r['data']:
                        all_data.append({"date": e['period'], "keyword": r['title'], "ratio": e['ratio'], "age_group": age_label})
        
        if all_data:
            df = pd.DataFrame(all_data)
            df.to_csv(OUTPUT_DIR / "racing_trends_age.csv", index=False, encoding='utf-8-sig')
            st.success("✅ 트렌드 데이터 저장 완료!")
            
        st.write("💬 소셜 검색 결과 수집 중...")
        search_results = []
        for kw in keywords[:2]: # 시간 관계상 주요 키워드만
            for dom in ["blog", "news"]:
                url = f"https://openapi.naver.com/v1/search/{dom}.json?query={urllib.parse.quote(kw)}&display=20"
                res = call_naver_api(url)
                if res and 'items' in res:
                    for item in res['items']:
                        search_results.append({"keyword": kw, "domain": dom, "title": item['title'].replace("<b>","").replace("</b>",""), "link": item['link'], "description": item['description'].replace("<b>","").replace("</b>",""), "date": item.get('postdate') or item.get('pubDate', '')})
        
        if search_results:
            pd.DataFrame(search_results).to_csv(OUTPUT_DIR / "racing_search_results.csv", index=False, encoding='utf-8-sig')
            st.success("✅ 소셜 데이터 저장 완료!")
        
        status.update(label="✅ 수집 완료! 페이지를 새로고침합니다.", state="complete")
        st.cache_data.clear()
        st.rerun()

# 데이터 로드 함수
# 데이터 로드 함수 (인코딩 보정 및 예외 처리 강화)
@st.cache_data
def load_data():
    trend_path = OUTPUT_DIR / "racing_trends_age.csv"
    search_path = OUTPUT_DIR / "racing_search_results.csv"
    
    debug_log = []
    
    def read_csv_with_encoding(path):
        if not path.exists():
            debug_log.append(f"❌ '{path.name}' 파일을 찾을 수 없습니다. (경로: {path})")
            return pd.DataFrame()
        
        # 순차적으로 인코딩 시도 (한글 깨짐 방지)
        for encoding in ['utf-8-sig', 'utf-8', 'cp949']:
            try:
                df = pd.read_csv(path, encoding=encoding)
                debug_log.append(f"✅ '{path.name}' 로드 성공 (인코딩: {encoding}, Shape: {df.shape})")
                return df
            except Exception:
                continue
        
        debug_log.append(f"❌ '{path.name}' 로드 실패 (모든 인코딩 시도 실패)")
        return pd.DataFrame()

    trend_df = read_csv_with_encoding(trend_path)
    search_df = read_csv_with_encoding(search_path)
    
    if not trend_df.empty and 'date' in trend_df.columns:
        trend_df['date'] = pd.to_datetime(trend_df['date'])
        
    return trend_df, search_df, debug_log

trend_df, search_df, debug_log = load_data()

# 사이드바 설정
with st.sidebar:
    st.header("📊 분석 필터")
    
    if not trend_df.empty:
        available_keywords = trend_df['keyword'].unique().tolist()
        selected_keywords = st.multiselect("분석 키워드", options=available_keywords, default=available_keywords[:3])
        
        available_ages = trend_df['age_group'].unique().tolist()
        selected_ages = st.multiselect("연령대 필터", options=available_ages, default=["Total", "20-24", "30-34", "40-44", "50-54"])
        
        if st.button("🔄 실시간 데이터 다시 수집"):
            collect_realtime_data()
    else:
        st.error("🚨 수집된 데이터가 없습니다!")
        if st.button("📡 지금 실시간 데이터 수집하기"):
            collect_realtime_data()

st.divider()

if trend_df.empty:
    st.info("수집된 데이터가 없습니다. `src/collector.py`를 실행하여 데이터를 수집하세요.")
else:
    tab1, tab2, tab3, tab4 = st.tabs(["📈 트렌드 분석", "👥 연령대별 비교", "🗺️ 히트맵 분석", "💬 소셜 인사이트"])
    
    with tab1:
        st.subheader("검색어별 트렌드 (Total)")
        total_df = trend_df[(trend_df['age_group'] == 'Total') & (trend_df['keyword'].isin(selected_keywords))]
        
        if not total_df.empty:
            fig = px.line(total_df, x="date", y="ratio", color="keyword", 
                          title="일별 검색 클릭 트렌드", template="plotly_white", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("선택한 키워드에 대한 데이터가 없습니다.")

    with tab2:
        st.subheader("연령대별 검색 선호도 비교")
        # 특정 키워드 하나를 선택해서 연령별 비교
        target_kw = st.selectbox("비교할 키워드 선택", options=selected_keywords)
        
        age_compare_df = trend_df[(trend_df['keyword'] == target_kw) & (trend_df['age_group'].isin(selected_ages))]
        
        if not age_compare_df.empty:
            fig_age = px.line(age_compare_df, x="date", y="ratio", color="age_group", 
                               title=f"'{target_kw}' 키워드 연령대별 트렌드", template="plotly_white")
            st.plotly_chart(fig_age, use_container_width=True)
            
            # 평균 검색량 바 차트
            avg_age = age_compare_df.groupby("age_group")["ratio"].mean().reset_index().sort_values("ratio", ascending=False)
            fig_bar = px.bar(avg_age, x="age_group", y="ratio", color="age_group", 
                             title=f"'{target_kw}' 연령대별 평균 관심도", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.write("데이터가 없습니다.")

    with tab3:
        st.subheader("연령대 x 키워드 관심도 히트맵")
        # 히트맵을 위해 연령대별 평균 ratio 계산
        heatmap_data = trend_df[trend_df['age_group'] != 'Total'].groupby(["keyword", "age_group"])["ratio"].mean().unstack()
        
        fig_heat = px.imshow(heatmap_data, text_auto=True, color_continuous_scale='Viridis',
                             title="키워드별 연령대별 관심도 지수 (평균 Ratio)")
        st.plotly_chart(fig_heat, use_container_width=True)
        
        st.info("Ratio는 해당 기간 내 최대 검색량을 100으로 잡은 상대적인 수치입니다.")

    with tab4:
        st.subheader("최신 소셜 및 뉴스 콘텐츠")
        if not search_df.empty:
            domain_filter = st.multiselect("채널 선택", options=search_df['domain'].unique(), default=search_df['domain'].unique())
            filtered_search = search_df[search_df['domain'].isin(domain_filter) & search_df['keyword'].isin(selected_keywords)]
            
            for index, row in filtered_search.head(20).iterrows():
                with st.container():
                    st.markdown(f"**[{row['domain'].upper()}] {row['title']}** ({row['date']})")
                    st.write(row['description'])
                    st.markdown(f"[링크 바로가기]({row['link']})")
                    st.divider()
        else:
            st.write("소셜 검색 결과 데이터가 없습니다.")

# 하단 정보 및 디버깅
st.sidebar.markdown("---")
with st.sidebar.expander("🔍 데이터 로드 디버그 정보", expanded=False):
    for log in debug_log:
        st.write(log)
    st.write(f"**BASE_DIR:** `{BASE_DIR}`")
    st.write(f"**OUTPUT_DIR:** `{OUTPUT_DIR}`")

st.sidebar.write(f"최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
