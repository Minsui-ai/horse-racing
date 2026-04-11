import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib.request
import json
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer

# --- 1. 기본 환경 설정 ---
st.set_page_config(page_title="Pet Market Intelligence", layout="wide", initial_sidebar_state="expanded")

# 프리미엄 디자인 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background-color: #0e1117; color: #ffffff; }
    .rising-card { padding: 20px; border-radius: 15px; background: linear-gradient(135deg, #1e2130 0%, #2b3040 100%); border: 1px solid #3d4255; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.4); }
    .rising-rank { font-size: 24px; font-weight: 800; color: #ff4b4b; }
    .rising-title { font-size: 20px; font-weight: 600; color: #ffffff; }
    .rising-percent { color: #00ff88; font-weight: 700; }
    .marketing-box { background: rgba(255, 255, 255, 0.05); border-left: 4px solid #4b8bff; padding: 10px; margin: 5px 0; border-radius: 4px; }
    .analyst-insight { background-color: #161b22; border-radius: 10px; padding: 15px; border-left: 5px solid #ffcc00; margin-top: 10px; font-size: 14px; line-height: 1.6; color: #e6edf3; }
</style>
""", unsafe_allow_html=True)

OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
TREND_FILE = os.path.join(OUTPUT_DIR, "market_trends_detailed.csv")
SEARCH_FILE = os.path.join(OUTPUT_DIR, "social_search_results.csv")

# --- 2. 핵심 로직 함수 (API & 데이터 분석) ---

def call_naver_api(url, body):
    try:
        client_id = st.secrets["NAVER_CLIENT_ID"]
        client_secret = st.secrets["NAVER_CLIENT_SECRET"]
    except:
        st.error("🔑 API 키 설정을 확인해주세요 (st.secrets: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)")
        return None
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    request.add_header("Content-Type", "application/json")
    
    try:
        response = urllib.request.urlopen(request, data=body.encode("utf-8") if body else None)
        if response.getcode() == 200:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        msg = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
        st.error(f"⚠️ API 에러: {msg}")
    return None

def collect_all_data(kws, start, end, age_grps, genders):
    # Trend Data
    url = "https://openapi.naver.com/v1/datalab/search"
    age_map = {"20대": ["3", "4"], "30대": ["5", "6"], "40대": ["7", "8"], "50대": ["9", "10"]}
    results = []
    
    # 성별 코드 매핑 (None: 전체, 'm': 남성, 'f': 여성)
    gender_map = {"전체": None, "남성": "m", "여성": "f"}
    selected_genders = [gender_map[g] for g in genders]
    
    total_steps = len(kws) * len(age_grps) * len(selected_genders)
    progress_bar = st.progress(0)
    step = 0

    for kw in kws:
        for ag in age_grps:
            age_codes = age_map.get(ag, [])
            for gen in selected_genders:
                body = {
                    "startDate": start,
                    "endDate": end,
                    "timeUnit": "date",
                    "keywordGroups": [{"groupName": kw, "keywords": [kw]}],
                    "ages": age_codes,
                    "gender": gen
                }
                data = call_naver_api(url, json.dumps(body))
                if data:
                    for res in data['results']:
                        for row in res['data']:
                            results.append({
                                'date': row['period'],
                                'keyword': kw,
                                'age_group': ag,
                                'gender': "남성" if gen == 'm' else "여성" if gen == 'f' else "전체",
                                'ratio': row['ratio']
                            })
                step += 1
                progress_bar.progress(step / total_steps)
    
    df_t = pd.DataFrame(results)
    if not df_t.empty:
        df_t.to_csv(TREND_FILE, index=False, encoding='utf-8-sig')

    # Social Data
    s_url = "https://openapi.naver.com/v1/search/webkr.json"
    s_results = []
    for kw in kws:
        res = call_naver_api(f"{s_url}?query={urllib.parse.quote(kw)}&display=100", None)
        if res:
            for itm in res['items']:
                domain = "blog" if "blog.naver.com" in itm['link'] else "cafe" if "cafe.naver.com" in itm['link'] else "news" if "news.naver.com" in itm['link'] else "other"
                s_results.append({
                    'keyword': kw,
                    'title': re.sub('<[^>]*>', '', itm['title']),
                    'description': re.sub('<[^>]*>', '', itm['description']),
                    'link': itm['link'],
                    'domain': domain,
                    'date': datetime.now().strftime("%Y-%m-%d")
                })
    df_s = pd.DataFrame(s_results)
    if not df_s.empty:
        df_s.to_csv(SEARCH_FILE, index=False, encoding='utf-8-sig')
    
    progress_bar.empty()
    return df_t, df_s

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        df = pd.read_csv(file)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        # 중복 데이터 제거 및 공백 제거로 데이터 청결도 확보
        df = df.drop_duplicates()
        if 'age_group' in df.columns:
            df['age_group'] = df['age_group'].str.strip()
        return df
    return pd.DataFrame()

# --- 3. 사이드바 UI ---
st.sidebar.title("🐾 Market Intel Settings")
st.sidebar.markdown("---")
kw_input = st.sidebar.text_input("🔍 분석 키워드 (컴마 구분)", "강아지 사료, 강아지 영양제, 강아지 간식")
keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
col_d1, col_d2 = st.sidebar.columns(2)
start_d = col_d1.date_input("시작일", datetime.now() - timedelta(days=90))
end_d = col_d2.date_input("종료일", datetime.now())

age_selection = st.sidebar.multiselect("👥 연령대 선택", ["20대", "30대", "40대", "50대"], ["20대", "30대", "40대", "50대"])
gender_selection = st.sidebar.multiselect("🚻 성별 선택", ["전체", "남성", "여성"], ["전체", "남성", "여성"])

if st.sidebar.button("🚀 실시간 데이터 동기화", use_container_width=True):
    with st.spinner("네이버 API에서 데이터를 가져오는 중..."):
        collect_all_data(keywords, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), age_selection, gender_selection)
        st.cache_data.clear()
        st.rerun()

# --- 4. 메인 대시보드 화면 ---
st.title("🐾 반려견 마켓 인텔리전스 대시보드")
st.caption("실시간 검색 트렌드 및 연령/성별 심층 분석 리포트")

df_trend = load_data(TREND_FILE)
df_search = load_data(SEARCH_FILE)

def perform_tfidf(texts):
    if not texts or len(texts) < 3: return pd.DataFrame()
    vectorizer = TfidfVectorizer(max_features=30)
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()
    sums = tfidf_matrix.sum(axis=0)
    data = [(name, sums[0, col]) for col, name in enumerate(feature_names)]
    return pd.DataFrame(data, columns=['키워드', '점수']).sort_values(by='점수', ascending=False)

if not df_trend.empty:
    with st.expander("🔍 데이터 품질 진단 (Health Check)"):
        st.write(f"📊 **데이터 규모**: {df_trend.shape[0]} 행, {df_trend.shape[1]} 열")
        col_c1, col_c2 = st.columns(2)
        col_c1.write("✅ 상위 5건"); col_c1.dataframe(df_trend.head())
        col_c2.write("✅ 하위 5건"); col_c2.dataframe(df_trend.tail())
        st.write("📈 기술통계 요약", df_trend.describe())
        st.write(f"🔄 중복: {df_trend.duplicated().sum()}건 | 결측치: {df_trend.isna().sum().sum()}건")

    # 사이드바 필터 실시간 적용
    df_filtered = df_trend[
        (df_trend['age_group'].isin(age_selection)) & 
        (df_trend['gender'].isin(gender_selection))
    ]

    tabs = st.tabs(["🚀 라이징 테마", "📊 트렌드 비교", "👥 타겟 세그먼트", "💬 소셜 분석"])

    with tabs[0]: # 라이징 테마
        st.subheader("🔥 전주 대비 급상승 키워드 (Rising Keywords)")
        latest = df_filtered['date'].max()
        this_w = df_filtered[(df_filtered['date'] > (latest - timedelta(days=7))) & (df_filtered['gender'] == '전체')]
        prev_w = df_filtered[(df_filtered['date'] <= (latest - timedelta(days=7))) & (df_filtered['date'] > (latest - timedelta(days=14))) & (df_filtered['gender'] == '전체')]
        
        rising_res = []
        for kw in keywords:
            t_val = this_w[this_w['keyword'] == kw]['ratio'].mean()
            p_val = prev_w[prev_w['keyword'] == kw]['ratio'].mean()
            if not pd.isna(t_val) and not pd.isna(p_val) and p_val > 0:
                rate = ((t_val - p_val) / p_val) * 100
                rising_res.append({"키워드": kw, "증가율": round(rate, 2)})
        
        rising_df = pd.DataFrame(rising_res).sort_values("증가율", ascending=False).head(3)
        
        if not rising_df.empty:
            cols = st.columns(3)
            for idx, row in enumerate(rising_df.iterrows()):
                with cols[idx]:
                    st.markdown(f'<div class="rising-card"><div class="rising-rank">TOP {idx+1}</div><div class="rising-title">{row[1]["키워드"]}</div><div class="rising-percent">{row[1]["증가율"]}% ↑</div></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("💡 연령대별 타겟 메시징 전략")
            target = rising_df.iloc[0]['키워드']
            st.info(f"선정 키워드: **{target}**")
            m_c1, m_c2 = st.columns(2)
            with m_c1:
                st.markdown(f'<div class="marketing-box"><strong>20대:</strong> 트렌디한 감성으로 다가가는 "{target}" 갓생 아이템</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="marketing-box"><strong>30대:</strong> 바쁜 일상을 돕는 효율적인 "{target}" 솔루션</div>', unsafe_allow_html=True)
            with m_c2:
                st.markdown(f'<div class="marketing-box"><strong>40대:</strong> 반려견의 건강과 여유를 위한 프리미엄 "{target}"</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="marketing-box"><strong>50대:</strong> 소중한 가족을 위한 진심 어린 선택, "{target}" 보양</div>', unsafe_allow_html=True)
            
            st.markdown(f'<div class="analyst-insight"><strong>📢 분석가 제언:</strong> "{target}" 키워드의 {rising_df.iloc[0]["증가율"]}% 상승은 시장 내 유의미한 변곡점입니다. 특히 남녀 비중과 연령별 분포를 고려했을 때, 감성 소구(20대)와 신뢰성 강조(50대) 전략이 주효할 것으로 판단됩니다.</div>', unsafe_allow_html=True)

    with tabs[1]: # 트렌드 비교 (차트 1-3)
        st.subheader("1. 키워드별 검색 시계열 비교")
        # 필터링된 데이터 사용 및 범례 명확화
        fig1 = px.line(
            df_filtered[df_filtered['gender'] == '전체'], 
            x='date', y='ratio', color='keyword', line_dash='age_group',
            title="[그래프 01] 키워드-연령별 통합 시나리오",
            labels={'ratio': '검색지수', 'date': '날짜', 'age_group': '연령대', 'keyword': '키워드'}
        )
        fig1.update_layout(legend_title="키워드 및 연령대")
        st.plotly_chart(fig1, use_container_width=True)
        st.info("💡 **분석 의견**: 이 시계열 차트는 선택된 키워드와 연령대의 검색 비중을 보여줍니다. 사이드바 필터를 통해 특정 세그먼트만 집중적으로 비교 분석할 수 있습니다.")

        st.subheader("2. 성별 검색 트렌드 비교 (Gender Focus)")
        # 현재 존재하는 키워드만 선택지에 노출
        available_kws = df_filtered['keyword'].unique()
        gender_kw = st.selectbox("성별 분석 키워드", available_kws if len(available_kws)>0 else keywords)
        fig2 = px.line(
            df_filtered[(df_filtered['keyword'] == gender_kw) & (df_filtered['gender'] != '전체')], 
            x='date', y='ratio', color='gender', 
            title=f"[그래프 02] '{gender_kw}' 남녀 검색량 추이",
            labels={'ratio': '검색지수', 'gender': '성별'}
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.info("💡 **분석 의견**: 남녀별 검색 성향 차이를 분석합니다. 남녀 성향이 뚜렷하게 갈리는 경우 타겟팅 광고 채널 선정의 기초 자료가 됩니다.")

        st.subheader("3. 요일별 열지도 (Activity Heatmap)")
        df_filtered['day'] = df_filtered['date'].dt.day_name()
        h_pivot = df_filtered[df_filtered['gender'] == '전체'].pivot_table(index='keyword', columns='day', values='ratio', aggfunc='mean')
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        h_pivot = h_pivot.reindex(columns=[d for d in days_order if d in h_pivot.columns])
        fig3 = px.imshow(h_pivot, color_continuous_scale='Blues', title="[그래프 03] 요일별 평균 검색 활동도")
        st.plotly_chart(fig3, use_container_width=True)

    with tabs[2]: # 세그먼트 분석 (차트 4-7)
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.subheader("4. 연령별 평균 관심도 비중")
            age_data = df_filtered[df_filtered['gender'] == '전체'].groupby('age_group')['ratio'].mean().reset_index()
            fig4 = px.pie(age_data, values='ratio', names='age_group', hole=0.4, title="[그래프 04] 연령별 관심도 점유율")
            st.plotly_chart(fig4, use_container_width=True)
        with col_s2:
            st.subheader("5. 성별 시장 참여 비중")
            gen_data = df_filtered[df_filtered['gender'] != '전체'].groupby('gender')['ratio'].mean().reset_index()
            fig5 = px.bar(gen_data, x='gender', y='ratio', color='gender', title="[그래프 05] 남녀별 평균 검색지수 비교")
            st.plotly_chart(fig5, use_container_width=True)
        
        st.subheader("6. 타겟 세그먼트 트리맵 (Keyword-Age-Gender)")
        fig6 = px.treemap(
            df_filtered[df_filtered['gender'] != '전체'], 
            path=['keyword', 'gender', 'age_group'], values='ratio', 
            title="[그래프 06] 시장 세분화 구조 (키워드/성별/연령)"
        )
        st.plotly_chart(fig6, use_container_width=True)
        
        st.subheader("7. 연령대별 변동성 진단 (Volatility Box)")
        fig7 = px.box(df_filtered, x='age_group', y='ratio', color='gender', title="[그래프 07] 속성별 데이터 분산 및 이상치 식별")
        st.plotly_chart(fig7, use_container_width=True)
        st.info("💡 **분석 의견**: 박스 플롯을 통해 데이터의 안정성을 평가합니다. 특정 속성에서 긴 수염이나 많은 이상치는 시장이 외부 자극에 매우 민감하게 반응하고 있음을 나타내며, 이는 곧 마케팅의 기회와 리스크가 공존함을 의미합니다.")

    with tabs[3]: # 소셜 분석 (차트 8-10)
        if not df_search.empty:
            st.subheader("8. TF-IDF 기반 소셜 텍스트 마이닝")
            tf_df = perform_tfidf((df_search['title'] + " " + df_search['description']).tolist())
            if not tf_df.empty:
                fig8 = px.bar(tf_df.head(20), x='점수', y='키워드', orientation='h', title="[그래프 08] 소셜 미디어 핵심 키워드 중요도 (Top 20)")
                st.plotly_chart(fig8, use_container_width=True)
                st.write("📋 **상위 10개 핵심어 통계표**", tf_df.head(10))
            
            col_z1, col_z2 = st.columns(2)
            with col_z1:
                st.subheader("9. 정보 유통 채널 비중")
                fig9 = px.funnel(df_search['domain'].value_counts().reset_index(), x='count', y='domain', title="[그래프 09] 채널별 전파력 분석")
                st.plotly_chart(fig9, use_container_width=True)
            with col_z2:
                st.subheader("10. 채널-키워드 연관성 분석")
                ctab = pd.crosstab(df_search['domain'], df_search['keyword'])
                fig10 = px.imshow(ctab, text_auto=True, color_continuous_scale='Reds', title="[그래프 10] 도메인별 키워드 확산 히트맵")
                st.plotly_chart(fig10, use_container_width=True)
        else:
            st.warning("소셜 데이터를 수집해 주세요.")

else:
    st.info("👈 사이드바에서 분석 조건을 지정하고 동기화 버튼을 눌러주세요!")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.caption("Data Vision by 20-Year Analyst")
