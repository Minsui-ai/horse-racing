import streamlit as st
import json
import urllib.request

# 1. API 키 (반드시 본인의 것을 넣으세요)
CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]

def debug_naver_api():
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # [핵심] 20대(3,4)와 30대(5,6) 데이터를 명시적으로 요청
    body = {
        "startDate": "2026-03-01",
        "endDate": "2026-04-09",
        "timeUnit": "month", # 데이터 양을 확인하기 위해 단위를 '월'로 변경해봅니다.
        "keywordGroups": [
            {
                "groupName": "테스트", 
                "keywords": ["삼성전자"] # 가장 확실한 키워드로 테스트
            }
        ],
        "ages": ["3", "4", "5", "6"] 
    }

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    req.add_header("Content-Type", "application/json")

    try:
        response = urllib.request.urlopen(req, data=json.dumps(body).encode("utf-8"))
        res_code = response.getcode()
        
        if res_code == 200:
            data = json.loads(response.read().decode("utf-8"))
            st.success("API 호출 자체는 성공했습니다!")
            
            # [디버깅] 네이버가 준 생짜 데이터를 그대로 출력합니다.
            st.json(data) 
            
            # 데이터 구조 확인 루프
            for result in data['results']:
                st.write(f"키워드 그룹: {result['title']}")
                if not result.get('data'):
                    st.error("해당 연령대의 데이터가 존재하지 않습니다. (검색량 부족)")
                else:
                    for entry in result['data']:
                        st.code(f"날짜: {entry['period']}, 연령코드: {entry.get('age')}, 지수: {entry['ratio']}")
        
    except Exception as e:
        st.error(f"접속 실패: {str(e)}")

st.title("네이버 API 끝장 디버깅")
if st.button("지금 바로 데이터 강제 호출"):
    debug_naver_api()
