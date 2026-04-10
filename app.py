import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib.request
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer

# --- 1. 환경 설정 및 초기화 ---
st.set_page_config(page_title="Racing Market Intelligence", layout="wide", initial_sidebar_state="expanded")

# CSS 스타일링 (Premium Look)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    .main {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        background-color: #1e2130;
        border-radius: 10px 10px 0 0;
        gap: 10px;
        padding-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# 디렉토리 설정
OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

TREND_FILE = os.path.join(OUTPUT_DIR, "racing_trends_age.csv")
SEARCH_FILE = os.path.join(OUTPUT_DIR, "racing_search_results.csv")

# --- 2. API 연동 함수 ---

def call_naver_api(url, body):
    client_id = st.secrets["NAVER_CLIENT_ID"]
    client_secret = st.secrets["NAVER_CLIENT_SECRET"]
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    request.add_header("Content-Type", "application/json")
    
    try:
        response = urllib.request.urlopen(request, data=body.encode("utf-8"))
        rescode = response.getcode()
        if rescode == 200:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        st.error(f"❌ API 요청 중 오류 발생: {str(e)}")
        if hasattr(e, 'read'):
            error_msg = e.read().decode('utf-8')
            st.error(f"상세 에러 내용: {error_msg}")
    return None

def collect_trends(keywords, start_date, end_date, age_groups):
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # 네이버 연령대 코드 매핑 (1: 0-12, 2: 13-18 ... 5: 35-39, 6: 40-44, 7: 45-49, 8: 50-54, 9: 55-59, 10: 60+)
    # 20대: 3,4 | 30대: 5,6 | 40대: 7,8 | 50대: 9,10 대략적 매핑
    age_map = {
        "20대": ["3", "4"],
        "30대": ["5", "6"],
        "40대": ["7", "8"],
        "50대": ["9", "10"]
    }
    
    target_ages = []
    for g in age_groups:
        target_ages.extend(age_map.get(g, []))
    
    results = []
    # '전체' 데이터 수집
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords],
        "ages": [] # 전체
    }
    data_all = call_naver_api(url, json.dumps(body))
    if data_all:
        for group in data_all['results']:
            kw = group['title']
            for entry in group['data']:
                results.append({'date': entry['period'], 'keyword': kw, 'age_group': '전체', 'ratio': entry['ratio']})

    # 선택된 연령대별 데이터 수집
    for age_code in target_ages:
        body["ages"] = [age_code]
        data_age = call_naver_api(url, json.dumps(body))
        if data_age:
            # 코드백 매핑
            age_label = ""
            for k, v in age_map.items():
                if age_code in v: age_label = k; break
            
            for group in data_age['results']:
                kw = group['title']
                for entry in group['data']:
                    results.append({'date': entry['period'], 'keyword': kw, 'age_group': age_label + f"({age_code})", 'ratio': entry['ratio']})
    
    df = pd.DataFrame(results)
    if not df.empty:
        df.to_csv(TREND_FILE, index=False, encoding='utf-8-sig')
    return df

def collect_social(keywords):
    url = "https://openapi.naver.com/v1/search/webkr.json" # 웹 검색 결과 (블로그, 카페 등 포함 가능)
    all_results = []
    
    for kw in keywords:
        query = urllib.parse.quote(kw)
        api_url = f"{url}?query={query}&display=50"
        data = call_naver_api(api_url, "")
        if data and 'items' in data:
            for item in data['items']:
                domain = "other"
                if "blog.naver.com" in item['link']: domain = "blog"
                elif "cafe.naver.com" in item['link']: domain = "cafe"
                
                all_results.append({
                    'keyword': kw,
                    'title': item['title'].replace("<b>", "").replace("</b>", ""),
                    'description': item['description'].replace("<b>", "").replace("</b>", ""),
                    'link': item['link'],
                    'domain': domain,
                    'date': datetime.now().strftime("%Y-%m-%d")
                })
    
    df = pd.DataFrame(all_results)
    if not df.empty:
        df.to_csv(SEARCH_FILE, index=False, encoding='utf-8-sig')
    return df

# --- 3. UI 구성 (사이드바) ---

st.sidebar.title("🏇 Market Intel Settings")
st.sidebar.markdown("---")

kw_input = st.sidebar.text_input("🔍 분석 키워드 (쉼표 구분)", value="경마, 마사회")
keywords = [k.strip() for k in kw_input.split(",") if k.strip()]

col_d1, col_d2 = st.sidebar.columns(2)
with col_d1:
    start_d = st.sidebar.date_input("시작일", datetime.now() - timedelta(days=90))
with col_d2:
    end_d = st.sidebar.date_input("종료일", datetime.now())

selected_age_groups = st.sidebar.multiselect("👥 분석 연령대", ["20대", "30대", "40대", "50대"], default=["30대", "40대"])

if st.sidebar.button("🚀 데이터 실시간 동기화", help="네이버 API를 통해 최신 데이터를 수집합니다."):
    with st.spinner("네이버 API에서 데이터를 가져오는 중..."):
        collect_trends(keywords, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), selected_age_groups)
        collect_social(keywords)
        st.sidebar.success("✅ 동기화 완료!")
        st.rerun()

# --- 4. 데이터 로드 ---

@st.cache_data
def load_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path, parse_dates=['date'] if 'date' in pd.read_csv(file_path, nrows=1).columns else None)
    return pd.DataFrame()

df_trend = load_data(TREND_FILE)
df_search = load_data(SEARCH_FILE)

# --- 5. 대시보드 메인 콘텐츠 ---

st.title("🏇 경마 마켓 인텔리전스 실시간 대시보드")
st.markdown("---")

def perform_tfidf(texts):
    if not texts or len(texts) < 3: return pd.DataFrame()
    vectorizer = TfidfVectorizer(max_features=30)
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()
        sums = tfidf_matrix.sum(axis=0)
        data = [(name, sums[0, col]) for col, name in enumerate(feature_names)]
        return pd.DataFrame(data, columns=['키워드', '점수']).sort_values(by='점수', ascending=False)
    except:
        return pd.DataFrame()

if not df_trend.empty:
    # 데이터 탐색 헤더
    with st.expander("🔍 데이터 기초 탐색 (Data Health Check)"):
        st.write(f"📊 **데이터 규모**: {df_trend.shape[0]} 행, {df_trend.shape[1]} 열")
        st.columns(2)[0].write("✅ **상위 5개 데이터**")
        st.columns(2)[0].dataframe(df_trend.head())
        st.columns(2)[1].write("✅ **하위 5개 데이터**")
        st.columns(2)[1].dataframe(df_trend.tail())
        
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            st.write("🛠️ **기본 정보**")
            buffer = pd.io.common.StringIO()
            df_trend.info(buf=buffer)
            st.text(buffer.getvalue())
        with col_i2:
            st.write("🔄 **중복 및 결측치**")
            st.write(f"- 중복 행: {df_trend.duplicated().sum()}")
            st.write(f"- 결측치 합계: {df_trend.isnull().sum().sum()}")

    tabs = st.tabs(["📉 트렌드 시계열", "👥 인구통계분석", "🧬 통계/상관분석", "💬 소셜/텍스트"])
    
    # 그래프를 위한 공통 필터링
    df_trend['date'] = pd.to_datetime(df_trend['date'])
    sel_keywords = df_trend['keyword'].unique()
    sel_ages = df_trend['age_group'].unique()

    with tabs[0]:
        # [그래프 1] 라인 차트
        st.subheader("1. 키워드별 검색 통합 트렌드")
        fig1 = px.line(df_trend[df_trend['age_group'] == '전체'], x='date', y='ratio', color='keyword',
                       title="[그래프 01] 날짜별 검색 관심도 추이 (전체 기준)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.info("💡 **분석 의견**: 이 그래프는 선택한 키워드의 시간 흐름에 따른 절대적인 검색량 변화를 보여줍니다. 특정 시점에서 발생하는 피크(Peak) 현상은 관련 검색어와 관련된 사회적 이슈나 마케팅 캠페인의 성공 여부를 판단하는 중요한 지표가 됩니다.")
        st.write("📊 **기술 통계표 (전체 기준)**", df_trend[df_trend['age_group'] == '전체'].groupby('keyword')['ratio'].describe())

        # [그래프 2] 이동평균 차트
        st.subheader("2. 7일 이동평균 트렌드 (Smoothing)")
        df_ma = df_trend[df_trend['age_group'] == '전체'].copy()
        df_ma['ratio_ma'] = df_ma.groupby('keyword')['ratio'].transform(lambda x: x.rolling(7).mean())
        fig2 = px.line(df_ma, x='date', y='ratio_ma', color='keyword', 
                       title="[그래프 02] 잡음 제거 후 검색 트렌드 흐름(7일 MA)", template="plotly_dark")
        st.plotly_chart(fig2, use_container_width=True)
        st.info("💡 **분석 의견**: 일별 데이터의 변동성이 클 경우 7일 이동평균선을 통해 시장의 중장기적인 흐름을 더 명확하게 파악할 수 있습니다. 완만한 우상향 혹은 우하향 곡선은 해당 키워드의 시장 생명력을 시사합니다.")

    with tabs[1]:
        col1, col2 = st.columns(2)
        with col1:
            # [그래프 3] 연령대별 평균 관심도
            st.subheader("3. 연령대별 평균 검색 강도")
            age_avg = df_trend[df_trend['age_group'] != '전체'].groupby('age_group')['ratio'].mean().reset_index()
            fig3 = px.bar(age_avg, x='age_group', y='ratio', color='age_group', text_auto='.1f',
                          title="[그래프 03] 연령별 평균 검색 관심도 비교", color_discrete_sequence=px.colors.sequential.Sunset)
            st.plotly_chart(fig3, use_container_width=True)
            st.info("💡 **분석 의견**: 각 연령대별 평균 검색 강도를 비교하여 주 타겟층을 정의합니다. 수치가 높을수록 해당 연령대에서의 인플레이션 수준이 높음을 의미하며 광고 타겟팅의 우선순위를 결정하는 근거가 됩니다.")
        
        with col2:
            # [그래프 4] 시장 점유율 파이 차트
            st.subheader("4. 관심도 시장 점유 비중")
            fig4 = px.pie(age_avg, values='ratio', names='age_group', hole=0.5,
                          title="[그래프 04] 연령대별 검색량 파이 점유율", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig4, use_container_width=True)
            st.info("💡 **분석 의견**: 전체 오디언스 중 특정 연령대가 차지하는 비중을 시각화합니다. 4050 세대의 비중이 압도적이라면 전통적인 마케팅 채널을, 2030 비중이 높다면 SNS 중심의 디지털 마케팅을 강화해야 합니다.")

        # [그래프 5] 변동성 박스플롯
        st.subheader("5. 연령별 검색 분포 및 변동성")
        fig5 = px.box(df_trend[df_trend['age_group'] != '전체'], x='age_group', y='ratio', color='age_group',
                      title="[그래프 05] 연령별 데이터 분산 및 이상치 분석", template="plotly_white")
        st.plotly_chart(fig5, use_container_width=True)
        st.info("💡 **분석 의견**: 박스플롯은 데이터의 안정성을 보여줍니다. 박스의 높이가 낮을수록 일관된 관심을, 높거나 수염이 길수록 변동성이 큼을 의미합니다. 충성 고객층이 두터운 연령대는 대개 좁은 범위를 형성합니다.")

    with tabs[2]:
        # [그래프 6] 요일별 히트맵
        st.subheader("6. 요일별 검색 집중도 패턴")
        df_heat = df_trend[df_trend['age_group'] == '전체'].copy()
        df_heat['weekday'] = df_heat['date'].dt.day_name()
        heat_pivot = df_heat.pivot_table(index='keyword', columns='weekday', values='ratio', aggfunc='mean')
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heat_pivot = heat_pivot.reindex(columns=days)
        fig6 = px.imshow(heat_pivot, color_continuous_scale='Viridis', title="[그래프 06] 키워드 x 요일별 평균 관심도 히트맵")
        st.plotly_chart(fig6, use_container_width=True)
        st.info("💡 **분석 의견**: 요일별 행동 패턴을 분석하면 어떤 요일에 소비자 커뮤니케이션을 강화해야 할지 알 수 있습니다. 특히 주말 직전의 검색 상승은 여가 활동으로서의 경마 소비 심리를 대변합니다.")

        # [그래프 7] 계층적 트리맵
        st.subheader("7. 키워드-연령 계층적 구조")
        fig7 = px.treemap(df_trend[df_trend['age_group'] != '전체'], path=['keyword', 'age_group'], values='ratio',
                          title="[그래프 07] 키워드 내 연령별 상대적 규모 트리맵")
        st.plotly_chart(fig7, use_container_width=True)
        st.info("💡 **분석 의견**: 면적으로 표현된 관심도 비중을 통해 어떤 키워드가 특정 연령대의 '메가 트렌드'인지 직관적으로 이해할 수 있게 도와줍니다. 상위 키워드와 하위 속성의 관계 구도를 명확히 합니다.")

        # [그래프 8] 산점도 (평균 vs 최대)
        st.subheader("8. 안정성 vs 폭발성 분석")
        sc_df = df_trend[df_trend['age_group'] != '전체'].groupby(['keyword', 'age_group'])['ratio'].agg(['mean', 'max']).reset_index()
        fig8 = px.scatter(sc_df, x='mean', y='max', color='keyword', size='max', text='age_group',
                          title="[그래프 08] 평균 관심도 대비 급등 여부 상관관계")
        st.plotly_chart(fig8, use_container_width=True)
        st.info("💡 **분석 의견**: 'Mean'은 기초 체력을, 'Max'는 이슈 대응력을 나타냅니다. 1사분면에 위치한 대상이 가장 매력적인 세그먼트이며, 4사분면은 충성도는 높으나 파급력이 부족한 세그メント로 보입니다.")

    with tabs[3]:
        if not df_search.empty:
            # [그래프 9] TF-IDF 키워드
            st.subheader("9. 소셜 텍스트 주요 키워드 추출 (TF-IDF)")
            all_text = (df_search['title'] + " " + df_search['description']).tolist()
            tfidf_res = perform_tfidf(all_text)
            if not tfidf_res.empty:
                fig9 = px.bar(tfidf_res.head(20), x='점수', y='키워드', orientation='h',
                              title="[그래프 09] 소셜 본문 내 중요 키워드 상위 20", color='점수')
                st.plotly_chart(fig9, use_container_width=True)
                st.write("📊 **TF-IDF 핵심 키워드 상세 리스트**", tfidf_res.head(10))
                st.info("💡 **분석 의견**: 복잡한 형태소 분석 없이 통계적 빈도와 중요도를 계산하는 TF-IDF 방식을 통해 선별된 핵심 단어들입니다. 이 단어들은 현재 시장에서 소비자들이 '경마'를 논할 때 함께 결부시키는 핵심 속성들입니다.")
            
            # [그래프 10] 채널 분포
            st.subheader("10. 정보 소스별 배포 현황")
            dom_dist = df_search['domain'].value_counts().reset_index()
            fig10 = px.funnel(dom_dist, x='count', y='domain', title="[그래프 10] 채널별 유통 비중")
            st.plotly_chart(fig10, use_container_width=True)
            st.info("💡 **분석 의견**: 카페, 블로그 등 소셜 미디어 플랫폼 간의 정보 유통 비중을 분석합니다. 카페 비중이 높으면 커뮤니티 활성도가 높고, 블로그 비중이 높으면 정보 공유 및 마케팅성 글이 많음을 예측합니다.")
            
            # 교차표
            st.subheader("📊 도메인별 키워드 유입 교차표")
            st.dataframe(pd.crosstab(df_search['domain'], df_search['keyword']), use_container_width=True)
        else:
            st.warning("수집된 소셜 데이터가 없습니다.")

else:
    st.info("좌측 사이드바 설정을 완료한 후 **[🚀 데이터 실시간 동기화]** 버튼을 눌러주세요.")

# 푸터
st.sidebar.markdown("---")
st.sidebar.caption(f"Last sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.caption("© 2024 Racing Intelligence Service")
