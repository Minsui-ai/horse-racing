import streamlit as st
import pandas as pd
import plotly.express as px
import os
import requests
from pathlib import Path
from datetime import datetime

# --- 1. 환경 설정 및 경로 보정 ---
# Streamlit Cloud 환경(/mount/src)과 로컬 환경 모두 대응
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

if not OUTPUT_DIR.exists():
    os.makedirs(OUTPUT_DIR)

# UI 설정
st.set_page_config(page_title="Racing Data Intelligence", layout="wide")

# --- 2. 데이터 수집 함수 (기존 collector.py 역할) ---
def fetch_naver_data(keyword):
    """네이버 API를 통해 실시간 데이터를 수집하는 예시 함수"""
    client_id = st.secrets.get("NAVER_CLIENT_ID")
    client_secret = st.secrets.get("NAVER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        st.error("API 키가 설정되지 않았습니다. Secrets 설정을 확인해주세요.")
        return None

    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=10"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('items', [])
    except Exception as e:
        st.error(f"데이터 수집 중 오류 발생: {e}")
    return None

# --- 3. 데이터 로드 및 수집 버튼 ---
@st.cache_data
def load_csv_data(file_name):
    path = OUTPUT_DIR / file_name
    if not path.exists():
        return pd.DataFrame()
    
    for encoding in ['utf-8-sig', 'utf-8', 'cp949']:
        try:
            return pd.read_csv(path, encoding=encoding)
        except:
            continue
    return pd.DataFrame()

# 사이드바에서 데이터 생성 제어
with st.sidebar:
    st.header("⚙️ 데이터 관리")
    if st.button("🔄 실시간 데이터 수집 실행"):
        with st.spinner("네이버에서 데이터를 가져오는 중..."):
            # 실제 구현 시에는 여기서 네이버 데이터랩/검색 API 결과를 CSV로 저장하는 로직 실행
            # 예시로 빈 파일 생성 에러 방지용 가짜 데이터 저장
            sample_data = pd.DataFrame({
                'date': [datetime.now().strftime('%Y-%m-%d')],
                'keyword': ['경마'],
                'ratio': [100],
                'age_group': ['Total']
            })
            sample_data.to_csv(OUTPUT_DIR / "racing_trends_age.csv", index=False, encoding='utf-8-sig')
            st.success("데이터 수집 완료! 앱을 재실행합니다.")
            st.rerun()

# --- 4. 메인 대시보드 로직 ---
st.title("🏇 Racing Market Intel Dashboard")

trend_df = load_csv_data("racing_trends_age.csv")
search_df = load_csv_data("racing_search_results.csv")

if trend_df.empty:
    st.warning("📊 아직 수집된 데이터가 없습니다. 왼쪽 사이드바에서 [데이터 수집 실행] 버튼을 눌러주세요.")
    st.info("💡 처음 배포 시에는 서버에 CSV 파일이 없으므로 수집 과정이 한 번 필요합니다.")
else:
    # 데이터가 있을 때만 차트 렌더링
    tab1, tab2 = st.tabs(["📈 트렌드 분석", "💬 소셜 인사이트"])
    
    with tab1:
        fig = px.line(trend_df, x="date", y="ratio", title="경마 검색 트렌드")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.write("수집된 데이터 샘플")
        st.dataframe(trend_df)
