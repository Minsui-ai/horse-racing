import streamlit as st
import pandas as pd
import plotly.express as px
import json
import urllib.request
from datetime import datetime, timedelta

# --- 1. API 키 로드 ---
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="Naver API Final Debugger", layout="wide")

# --- 2. API 호출 함수 (에러 상세 출력) ---
def fetch_naver_data(keywords, start_date, end_date, ages):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
        "ages": ages # ["3", "4", "5", "6"] 형태로 전달
    }
    
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    req.add_header("Content-Type", "application/json")
    
    try:
        res = urllib.request.urlopen(req, data=json.dumps(body).encode("utf-8"))
        return json.loads(res.read().decode("utf-8")), "SUCCESS"
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        return None, f"HTTP_{e.code}: {error_msg}"
    except Exception as e:
        return None, str(e)

# --- 3. 데이터 가공 ---
def process_data(data):
    if not data or "results" not in data:
        return pd.DataFrame()
    
    rows = []
    # 네이버 공식 가이드 기반 전체 매핑
    age_map = {
        '1':'0-12', '2':'13-18', '3':'19-24', '4':'25-29', '5':'30-34', 
        '6':'35-39', '7':'40-44', '8':'45-49', '9':'50-54', '10':'55-59', '11':'60+'
    }
    
    for result in data["results"]:
        title = result["title"]
        for entry in result.get("data", []):
            age_code = str(entry.get("age"))
            rows.append({
                "날짜": entry["period"],
                "키워드": title,
                "연령대": age_map.get(age_code, f"코드:{age_code}"),
                "검색지수": entry["ratio"]
            })
    return pd.DataFrame(rows)

# --- 4. 메인 화면 ---
st.title("🧪 네이버 데이터랩 권한 정밀 진단")

if not CLIENT_ID or not CLIENT_SECRET:
    st.error("🚨 API 키가 설정되지 않았습니다. Streamlit Secrets를 확인하세요.")
    st.stop()

with st.sidebar:
    st.header("⚙️ 테스트 설정")
    test_kw = st.text_input("테스트 키워드", "삼성전자")
    days = st.slider("조회 기간(일)", 7, 90, 30)
    
    # 모든 연령대를 체크해봅니다.
    all_ages = [str(i) for i in range(1, 12)]

if st.button("🔍 API 응답 구조 분석 시작"):
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    
    raw_data, status = fetch_naver_data([test_kw], start, end, all_ages)
    
    if "SUCCESS" in status:
        st.success("✅ API 연결 성공!")
        
        # 1. 원본 JSON 구조 확인 (가장 중요)
        with st.expander("📦 네이버 API 실제 응답 데이터 (Raw JSON)"):
            st.json(raw_age_data := raw_data["results"][0].get("data", []))
            if not raw_age_data:
                st.warning("⚠️ API는 성공했으나, 네이버가 보낸 'data' 리스트가 비어있습니다. 이는 해당 기간/키워드에 연령별 통계가 존재하지 않음을 의미합니다.")

        # 2. 결과 테이블 및 차트
        df = process_data(raw_data)
        if not df.empty:
            st.subheader(f"📈 '{test_kw}' 검색 추이")
            fig = px.line(df, x="날짜", y="검색지수", color="연령대")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df)
        else:
            st.info("데이터를 표로 변환할 수 없습니다. 위 JSON 데이터를 확인하세요.")
            
    else:
        st.error(f"❌ API 호출 실패: {status}")
        if "403" in status:
            st.markdown("""
            **403 에러 해결 방법:**
            1. [네이버 개발자 센터](https://developers.naver.com/apps/#/list) 접속
            2. 사용 중인 애플리케이션 클릭
            3. **API 설정** 탭에서 **데이터랩(검색어트렌드)**가 선택되어 있는지 확인
            4. **로그인 오픈 API 서비스 환경**에 현재 Streamlit URL이 등록되어 있는지 확인 (필요시 수정)
            """)
