import streamlit as st  # Streamlit 라이브러리 임포트
import pandas as pd  # 데이터 처리를 위한 Pandas 라이브러리 임포트
import plotly.express as px  # 시각화를 위한 Plotly Express 임포트
import plotly.graph_objects as go  # 세밀한 그래프 설정을 위한 Plotly Graph Objects 임포트
from datetime import datetime, timedelta  # 날짜 및 시간 처리를 위한 모듈 임포트
import os  # 운영체제 인터페이스(파일 경로 등) 임포트
import json  # JSON 데이터 파싱을 위한 라이브러리 임포트
import urllib.request  # HTTP 요청을 보내기 위한 라이브러리 임포트
import re  # 정규표현식 처리를 위한 라이브러리 임포트
from dotenv import load_dotenv  # 환경 변수 로드를 위한 dotenv 임포트

# 페이지 레이아웃 설정 (Wide 모드 및 타이틀, 아이콘 설정)
st.set_page_config(page_title="네이버 검색 인사이트 대시보드", layout="wide", page_icon="🛡️")

# API 인증 정보 로드 (Streamlit Cloud Secrets 또는 로컬 .env 호환 레이어)
try:
    # Streamlit Cloud 배포 환경이나 로컬 secrets.toml이 있는 경우
    if "NAVER_CLIENT_ID" in st.secrets:
        CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
        CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    else:
        raise KeyError  # 키가 없으면 로컬 환경으로 전환
except (FileNotFoundError, KeyError, Exception):
    # 로컬 개발 환경용 .env 로드 (secrets.toml이 없거나 에러 발생 시)
    load_dotenv()
    CLIENT_ID = os.getenv("NAVER_CLIENT_ID")  # 네이버 API 클라이언트 ID 가져오기
    CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")  # 네이버 API 클라이언트 시크릿 가져오기

# CSS를 활용한 대시보드 프리미엄 스타일링 정의
st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;  /* 메인 배경색 설정 */
    }
    .stMetric {
        background-color: #ffffff;  /* 메트릭 카드 배경색 */
        padding: 20px;  /* 내부 여백 */
        border-radius: 12px;  /* 테두리 둥글게 */
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);  /* 그림자 효과 */
        border: 1px solid #e0e0e0;  /* 테두리 선 */
    }
    div.stTabs [data-baseweb="tab-list"] {
        gap: 24px;  /* 탭 간격 */
    }
    div.stTabs [data-baseweb="tab"] {
        height: 50px;  /* 탭 높이 */
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 600;  /* 글자 굵기 */
        font-size: 16px;  /* 글자 크기 */
    }
    </style>
    """, unsafe_allow_html=True)

class NaverApi:
    """네이버 API 통신을 전담하는 클래스 정의"""
    def __init__(self, client_id, client_secret):
        self.client_id = client_id  # 초기화 시 클라이언트 ID 저장
        self.client_secret = client_secret  # 초기화 시 클라이언트 시크릿 저장

    def _call_api(self, url, method='GET', body=None):
        """내부 API 호출 공통 메서드"""
        try:
            request = urllib.request.Request(url)  # API 요청 객체 생성
            request.add_header("X-Naver-Client-Id", self.client_id)  # API 헤더에 ID 추가
            request.add_header("X-Naver-Client-Secret", self.client_secret)  # API 헤더에 시크릿 추가
            
            if method == 'POST':
                request.add_header("Content-Type", "application/json")  # POST 방식일 때 컨텐츠 타입 설정
                response = urllib.request.urlopen(request, data=body.encode("utf-8"))  # 바디 데이터를 인코딩하여 전송
            else:
                response = urllib.request.urlopen(request)  # GET 방식 요청 실행
                
            rescode = response.getcode()  # 응답 코드 확인
            if rescode == 200:
                return json.loads(response.read().decode('utf-8'))  # 성공 시 JSON 결과 반환
            else:
                st.error(f"API 에러 코드: {rescode}")  # 에러 코드 발생 시 화면에 표시
                return None
        except Exception as e:
            st.error(f"API 요청 중 오류 발생: {e}")  # 예외 상황 발생 시 에러 메시지 표시
            return None

    def get_datalab_trend(self, keywords, start_date, end_date, ages=None, gender=None, device=None):
        """네이버 데이터랩 통합검색어 트렌드 API 호출 메서드 (연령/성별/기기 필터 추가)"""
        url = "https://openapi.naver.com/v1/datalab/search"
        groups = [{"groupName": k, "keywords": [k]} for k in keywords]  # 검색어 그룹 생성
        body = {
            "startDate": start_date,  # 시작 날짜 설정
            "endDate": end_date,  # 종료 날짜 설정
            "timeUnit": "date",  # 단위 설정 (일간)
            "keywordGroups": groups  # 검색어 그룹 포함
        }
        # 선택적 필터 추가 (값이 있을 때만 포함)
        if ages: body["ages"] = ages
        if gender: body["gender"] = gender
        if device: body["device"] = device
        
        return self._call_api(url, method='POST', body=json.dumps(body, ensure_ascii=False))  # POST 방식으로 호출

    def search_basic(self, category, query, display=100):
        """쇼핑, 블로그, 카페 등 기본 검색 API 호출 메서드"""
        encText = urllib.parse.quote(query)  # 쿼리 텍스트를 URL 인코딩
        url = f"https://openapi.naver.com/v1/search/{category}.json?query={encText}&display={display}&sort=sim"
        return self._call_api(url)  # GET 방식으로 호출

@st.cache_data(show_spinner="📡 네이버 서버에서 데이터를 실시간으로 가져오는 중...")
def fetch_all_data(keywords, start_date, end_date, ages=None, gender=None, device=None):
    """모든 채널의 데이터를 수집하고 캐싱하는 함수 (필터 파라미터 추가)"""
    api = NaverApi(CLIENT_ID, CLIENT_SECRET)  # API 객체 생성
    
    # 1. 네이버 데이터랩 검색 트렌드 데이터 수집 (필터 적용)
    trend_res = api.get_datalab_trend(keywords, start_date, end_date, ages, gender, device)
    trend_df = pd.DataFrame()  # 결과 데이터프레임 초기화
    if trend_res and 'results' in trend_res:
        list_df = []
        for res in trend_res['results']:
            if 'data' in res:
                df = pd.DataFrame(res['data'])  # 개별 데이터프레임 생성
                df['keyword'] = res['title']  # 키워드 정보 추가
                df['period'] = pd.to_datetime(df['period'])  # 날짜 형식 변환
                list_df.append(df)
        if list_df:
            trend_df = pd.concat(list_df).reset_index(drop=True)  # 전체 통합 및 인덱스 초기화
    
    # 2. 통합 검색 결과(쇼핑, 블로그, 카페, 뉴스) 수집
    search_data = {cat: [] for cat in ['shop', 'blog', 'cafearticle', 'news']}
    for k in keywords:
        for cat in search_data.keys():
            res = api.search_basic(cat, k)  # 채널별 API 호출
            if res and 'items' in res:
                df = pd.DataFrame(res['items'])  # 검색 결과 아이템 로드
                df['query_keyword'] = k  # 검색 원천 키워드 기록
                # 데이터 정제: HTML 태그(<b> 등) 삭제
                if 'title' in df.columns:
                    df['title'] = df['title'].str.replace(r'<[^>]*>', '', regex=True)
                if 'description' in df.columns:
                    df['description'] = df['description'].str.replace(r'<[^>]*>', '', regex=True)
                df['search_category'] = cat  # 검색 카테고리 정보 기록 (에러 방지용)
                search_data[cat].append(df)
    
    final_search_data = {}  # 최종 통합 데이터 딕셔너리
    for cat, dfs in search_data.items():
        if dfs:
            final_search_data[cat] = pd.concat(dfs).reset_index(drop=True)  # 카테고리별 통합
        else:
            final_search_data[cat] = pd.DataFrame()  # 데이터 없을 시 빈 데이터프레임 생성
    
    return trend_df, final_search_data  # 트렌드 및 검색 결과 반환

def clean_token(text):
    """텍스트 정제 및 단어 단위 토큰화 함수"""
    text = re.sub(r'[^가-힣A-Za-z0-9\s]', '', str(text))  # 한글, 영문, 숫자, 공백 제외 제거
    return text.split()  # 공백 기준으로 단어 분할

# --- 사이드바 (Sidebar) UI 구성 ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/0/09/Naver_Line_Icon.png", width=50)
    st.title("네이버 인사이드 : 검색엔진")
    st.markdown("---")
    
    st.header("🔑 API 상태 확인")
    st.success("인증 정보 로드 완료" if CLIENT_ID else "인증 정보 없음")
    
    st.header("🔍 분석 키워드")
    input_keywords = st.text_input("콤마(,)로 여러 개 입력 가능", "핫팩, 선풍기")
    keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]  # 입력값을 리스트로 변환
    
    st.header("📅 분석 기간")
    default_start = datetime.now() - timedelta(days=90)  # 기본 시작일 (90일 전)
    start_dt = st.date_input("시작 날짜", default_start)
    end_dt = st.date_input("종료 날짜", datetime.now())  # 종료 날짜 (오늘)
    
    st.header("👥 타겟 필터 (트렌드)")
    age_map = {
        "0~12세": "1", "13~18세": "2", "19~24세": "3", "25~29세": "4",
        "30~34세": "5", "35~39세": "6", "40~44세": "7", "45~49세": "8",
        "50~54세": "9", "55~59세": "10", "60세 이상": "11"
    }
    selected_ages = st.multiselect("연령대 선택 (미선택 시 전체)", list(age_map.keys()))
    age_codes = [age_map[age] for age in selected_ages] if selected_ages else None
    
    gender_opt = st.radio("성별", ["전체", "여성", "남성"], horizontal=True)
    gender_code = {"여성": "f", "남성": "m"}.get(gender_opt)
    
    device_opt = st.radio("기기", ["전체", "모바일", "PC"], horizontal=True)
    device_code = {"모바일": "mo", "PC": "pc"}.get(device_opt)
    
    st.header("💰 쇼핑 가격 필터")
    p_min, p_max = st.slider("가격을 조절해 필터링하세요", 0, 1000000, (0, 500000), step=5000)
    
    run_btn = st.button("🚀 실시간 데이터 분석 실행", use_container_width=True)

# --- 메인 대시보드 화면 구성 ---
st.title("📈 네이버 실시간 시장 지능형 리포트")
filter_info = f" | 연령: {', '.join(selected_ages) if selected_ages else '전체'} | 성별: {gender_opt} | 기기: {device_opt}"
st.markdown(f"**현재 키워드:** {', '.join(keywords)} | **대상 기간:** {start_dt} ~ {end_dt}{filter_info}")

if run_btn or st.session_state.get('data_ready'):
    if run_btn:
        st.session_state['data_ready'] = False  # 실행 시 이전 결과 초기화
        # 실시간 데이터 호출 (새로운 필터 적용)
        trend_df, search_results = fetch_all_data(
            keywords, 
            start_dt.strftime('%Y-%m-%d'), 
            end_dt.strftime('%Y-%m-%d'),
            ages=age_codes,
            gender=gender_code,
            device=device_code
        )
        
        if trend_df.empty and all(df.empty for df in search_results.values()):
            st.error("불러올 수 있는 데이터가 없습니다. 요청 사항을 확인해 주세요.")
        else:
            st.session_state['trend_df'] = trend_df  # 세션에 트렌드 저장
            st.session_state['search_results'] = search_results  # 세션에 검색 결과 저장
            st.session_state['data_ready'] = True  # 로드 상태 업데이트

    if st.session_state.get('data_ready'):
        # 4가지 메인 탭 구성
        tab1, tab2, tab3, tab4 = st.tabs(["📊 데이터 프로파일링", "📈 마켓 트렌드", "💬 소셜 인사이트", "📁 원본 데이터"])
        
        trend_df = st.session_state['trend_df']
        search_results = st.session_state['search_results']
        
        # 1. 데이터 프로파일링 탭 (EDA)
        with tab1:
            st.header("📊 데이터 프로파일링 (EDA)")
            m1, m2, m3, m4 = st.columns(4)  # 4열 레이아웃
            m1.metric("분석 키워드 수", len(keywords))
            m2.metric("트렌드 기록 건수", len(trend_df))
            m3.metric("소셜 콘텐츠 건수", sum(len(df) for k, df in search_results.items() if k != 'shop'))
            m4.metric("수집된 상품 수", len(search_results['shop']))
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("데이터 결측치 및 품질 현황")
                missing_data = pd.DataFrame({
                    '채널(Channel)': list(search_results.keys()),
                    '결측치 합계': [df.isnull().sum().sum() for df in search_results.values()]
                })
                fig_missing = px.bar(missing_data, x='채널(Channel)', y='결측치 합계', color='채널(Channel)', template="plotly_white")
                st.plotly_chart(fig_missing, use_container_width=True)
            
            with c2:
                st.subheader("채널별 데이터 비중 (구성비)")
                dist_data = pd.DataFrame({
                    'Channel': list(search_results.keys()),
                    'Count': [len(df) for df in search_results.values()]
                })
                fig_dist = px.pie(dist_data, values='Count', names='Channel', hole=0.4)
                st.plotly_chart(fig_dist, use_container_width=True)
            
            st.subheader("쇼핑 데이터 기술통계 요약")
            shop_df = search_results['shop'].copy()
            if not shop_df.empty:
                shop_df['lprice'] = pd.to_numeric(shop_df['lprice'], errors='coerce')  # 가격 데이터 수치화
                st.dataframe(shop_df.describe().T, use_container_width=True)  # 기술통계 전치 출력

        # 2. 마켓 트랜드 및 쇼핑 상세 분석 탭
        with tab2:
            st.header("📈 검색 시장 트렌드 & 쇼핑 분석")
            # 검색량 변화 추이 그래프
            fig_trend = px.area(trend_df, x='period', y='ratio', color='keyword', 
                              title="네이버 검색어 상대 지수 변화 추이", line_group='keyword', template="plotly_white")
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.markdown("---")
            st.subheader("🛍️ 쇼핑 채널 구조 (Treemap & Sunburst)")
            
            if not shop_df.empty:
                # 사이드바에서 설정한 가격 필터 적용
                shop_filtered = shop_df[(shop_df['lprice'] >= p_min) & (shop_df['lprice'] <= p_max)]
                
                cc1, cc2 = st.columns(2)
                with cc1:
                    # 판매처별 트리맵 시각화
                    fig_tree = px.treemap(shop_filtered, path=[px.Constant("전체"), 'query_keyword', 'mallName'], 
                                        values='lprice', color='lprice', color_continuous_scale='Viridis',
                                        title="쇼핑몰별/키워드별 가격 가중치 구조")
                    st.plotly_chart(fig_tree, use_container_width=True)
                with cc2:
                    # 카테고리별 선버스트 분석
                    fig_sun = px.sunburst(shop_filtered, path=['query_keyword', 'category1', 'category2'],
                                         title="카테고리 상세 분류 위계 관찰")
                    st.plotly_chart(fig_sun, use_container_width=True)

        # 3. 소셜 및 여론 분석 탭
        with tab3:
            st.header("💬 소셜 네트워크 & 뉴스 미디어 여론 분석")
            
            # 검색 결과의 단어 빈도 분석
            combined_social = pd.concat([search_results['blog'], search_results['cafearticle'], search_results['news']])
            if not combined_social.empty:
                all_text = " ".join(combined_social['title'].astype(str))  # 모든 제목 통합
                tokens = clean_token(all_text)
                # 불용어(의미 없는 단어) 필터링
                stops = ['있는', '위한', '합니다', '에서', '그리고', '좋은', '추천', '선풍기', '핫팩', '네이버']
                final_words = [w for w in tokens if len(w) > 1 and w not in stops]
                
                if final_words:
                    word_freq = pd.Series(final_words).value_counts().head(30).reset_index()  # 상위 30개 단어 추출
                    word_freq.columns = ['Word', 'Frequency']
                    
                    # 핵심 키워드 막대 그래프
                    fig_words = px.bar(word_freq, x='Frequency', y='Word', orientation='h',
                                     title="핵심 관심사Top 30 (문맥 키워드)", color='Frequency',
                                     color_continuous_scale='Blues')
                    fig_words.update_layout(yaxis={'categoryorder':'total ascending'})  # 높은 순으로 정렬
                    st.plotly_chart(fig_words, use_container_width=True)
            
            st.markdown("---")
            st.subheader("키워드별 콘텐츠 채널 분포")
            fig_social_sun = px.sunburst(combined_social, path=['query_keyword', 'search_category'], 
                                        title="키워드별 - 채널 점유 분석")
            st.plotly_chart(fig_social_sun, use_container_width=True)

        # 4. 데이터 저장소 및 상세 검색 탭
        with tab4:
            st.header("📁 실시간 수집 데이터 탐색기")
            for cat, df in search_results.items():
                with st.expander(f"📌 {cat.upper()} 데이터 보기 (상세 정보)"):
                    st.dataframe(df, use_container_width=True)  # 원본 데이터프레임 노출
                    csv = df.to_csv(index=False).encode('utf-8-sig')  # 한글 깨짐 방지 인코딩
                    st.download_button(f"{cat.upper()} 데이터 다운로드", csv, 
                                     f"naver_{cat}_realtime.csv", "text/csv")
else:
    # 데이터 수집 전 안내 메시지 및 기본 이미지 노출
    st.info("👈 왼쪽 사이드바에서 검색어와 기간을 설정하고 '실시간 분석 실행' 버튼을 눌러주세요.")
    st.image("https://images.unsplash.com/photo-1460925895917-afdab827c52f?ixlib=rb-1.2.1&auto=format&fit=crop&w=1352&q=80", use_container_width=True)
