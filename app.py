# Korean-Movieimport streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ----------------------------------------------------
# 1. 페이지 기본 설정 및 제목
# ----------------------------------------------------
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 현황")

# ----------------------------------------------------
# 2. 한국 시간(KST) 기준 '어제' 날짜 계산하기
# ----------------------------------------------------
# 배포 서버(해외)의 시계와 상관없이 항상 한국 시간(UTC+9)을 기준으로 어제 날짜를 구합니다.
kst = timezone(timedelta(hours=9))
now_kst = datetime.now(kst)
yesterday_kst = now_kst - timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD)
target_dt = yesterday_kst.strftime("%Y%m%d")
# 화면 표시용 날짜 형식 (YYYY년 MM월 DD일)
formatted_date = yesterday_kst.strftime("%Y년 %m월 %d일")

st.subheader(f"📅 기준일: {formatted_date}")

# ----------------------------------------------------
# 3. KOBIS API 비밀키 불러오기 (Streamlit Secrets)
# ----------------------------------------------------
# Secrets에 KOBIS_KEY가 없으면 에러 안내 메시지를 띄우고 앱을 멈춥니다.
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키(KOBIS_KEY)를 찾을 수 없습니다.")
    st.info(
        """
        **💡 해결 방법:**
        1. **Streamlit Cloud**: 대시보드의 앱 설정(`Settings` -> `Secrets`) 메뉴로 이동합니다.
        2. 아래 양식대로 KOBIS API 인증키를 등록해 주세요.
           ```toml
           KOBIS_KEY = "여기에_발급받은_인증키_입력"
           ```
        3. **내 컴퓨터(로컬 실행 시)**: 프로젝트 폴더 안에 `.streamlit/secrets.toml` 파일을 만들고 동일하게 입력해 주세요.
        """
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# ----------------------------------------------------
# 4. KOBIS API 데이터 요청하기
# ----------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt
}

# 네트워크 통신 시도
try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()  # HTTP 연결에 문제가 발생하면 예외를 일으킵니다.
    data = response.json()
except Exception as e:
    st.error("🚨 KOBIS 서버에 연결하지 못했습니다.")
    st.info(
        """
        **💡 확인해 주세요:**
        - 인터넷 연결 상태가 정상인지 확인해 주세요.
        - 영화진흥위원회(KOBIS) 서버에 일시적인 점검이나 장애가 있을 수 있으니 잠시 후 다시 시도해 주세요.
        """
    )
    st.stop()

# ----------------------------------------------------
# 5. API 응답 에러 및 예외 처리
# ----------------------------------------------------
box_office_result = data.get("boxOfficeResult", {})

# KOBIS API는 인증키가 틀려도 HTTP 200 상태코드와 함께 'faultInfo' 객체를 응답합니다.
if "faultInfo" in data or "faultInfo" in box_office_result:
    fault_msg = data.get("faultInfo", {}).get("message", "인증 실패 또는 오류 발생")
    st.error(f"🚨 API 요청 오류 발생: {fault_msg}")
    st.info(
        """
        **💡 확인해 주세요:**
        - 입력하신 `KOBIS_KEY`가 정확한지 확인해 주세요.
        - 영화진흥위원회 Open API 웹사이트에서 발급받은 인증키의 일일 요청 제한량이 초과되었는지 확인해 주세요.
        """
    )
    st.stop()

# 영화 목록 추출
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 응답은 성공했으나 영화 목록이 비어 있는 경우
if not daily_list:
    st.warning("⚠️ 조회된 박스오피스 데이터가 없습니다.")
    st.info(
        """
        **💡 확인해 주세요:**
        - 오늘 일자 데이터 집계가 아직 진행 중일 수 있습니다. (KOBIS 집계 시점 안내 참조)
        - 집계 시스템 서버의 데이터 업데이트 시각을 기다려 주세요.
        """
    )
    st.stop()

# ----------------------------------------------------
# 6. 데이터 변환 및 정리
# ----------------------------------------------------
df = pd.DataFrame(daily_list)

# KOBIS API는 모든 숫자(관객수, 순위 등)를 문자열로 전달하므로 정수(int)형으로 변환합니다.
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# ----------------------------------------------------
# 7. 1위 영화 지표 카드 (3개)
# ----------------------------------------------------
top_1 = df.iloc[0]

st.markdown(f"### 🏆 1위 영화: **{top_1['movieNm']}**")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="🍿 어제 관객수", value=f"{top_1['audiCnt']:,} 명")
with col2:
    st.metric(label="👥 누적 관객수", value=f"{top_1['audiAcc']:,} 명")
with col3:
    st.metric(label="🖥️ 상영 스크린수", value=f"{top_1['scrnCnt']:,} 개")

st.divider()

# ----------------------------------------------------
# 8. 관객수 상위 5편 막대그래프
# ----------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화 비교")

# 상위 5개 영화 선택
top_5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
top_5_df.rename(columns={"movieNm": "영화명", "audiCnt": "어제 관객수"}, inplace=True)
top_5_df.set_index("영화명", inplace=True)

# 시각화 막대그래프 출력
st.bar_chart(top_5_df)

st.divider()

# ----------------------------------------------------
# 9. 전체 박스오피스 표 출력
# ----------------------------------------------------
st.subheader("📋 전체 순위 목록")

# 필요한 컬럼만 추출 및 이름 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 서식이 적용된 표 출력
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "관객수": st.column_config.NumberColumn("관객수", format="%d명"),
        "누적관객": st.column_config.NumberColumn("누적관객", format="%d명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d개"),
    }
)
