import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import Counter

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(page_title="당곡고 급식 다이어트 분석기", layout="wide")

API_KEY = st.secrets.get("NEIS_API_KEY", "")

# 당곡고등학교 정보
SCHOOL = {"학교명": "당곡고등학교", "시도교육청코드": "B10", "행정표준코드": "7010073"}

# 인기 메뉴 키워드 (맛있는 날 판단용 - 임의 기준)
TASTY_KEYWORDS = ["치킨", "피자", "돈까스", "탕수육", "떡볶이", "함박", "제육", "갈비", "볶음밥", "스파게티"]
UNTASTY_KEYWORDS = ["나물", "샐러드", "죽", "묵"]

# 디버깅 모드 (문제 해결되면 False로 변경)
DEBUG_MODE = True


# =========================================================
# 급식 정보 가져오기
# =========================================================
@st.cache_data(ttl=3600)
def get_meal_info(atpt_code, school_code, start_date, end_date):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": start_date,
        "MLSV_TO_YMD": end_date,
    }
    res = requests.get(url, params=params)

    if DEBUG_MODE:
        st.write("### 🔧 디버깅 정보")
        st.write("요청 URL:", res.url)
        st.write("응답 상태 코드:", res.status_code)
        try:
            st.json(res.json())
        except Exception as e:
            st.write("JSON 파싱 실패:", e)
            st.write("응답 원문:", res.text)

    try:
        data = res.json()
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError):
        return []

    result = []
    for r in rows:
        menu_raw = r.get("DDISH_NM", "")
        menu_list = clean_menu(menu_raw)
        cal_info = r.get("CAL_INFO", "0 Kcal").replace("Kcal", "").strip()
        try:
            calorie = float(cal_info)
        except ValueError:
            calorie = 0.0

        nutrition = parse_nutrition(r.get("NTR_INFO", ""))

        result.append({
            "날짜": r.get("MLSV_YMD"),
            "식사구분": r.get("MMEAL_SC_NM"),
            "메뉴": menu_list,
            "칼로리": calorie,
            "영양정보": nutrition
        })
    return result


def clean_menu(raw_menu):
    items = raw_menu.split("<br/>")
    cleaned = [re.sub(r"\(.*?\)", "", item).strip() for item in items]
    return [c for c in cleaned if c]


def parse_nutrition(ntr_str):
    nutrition = {}
    items = ntr_str.split("<br/>")
    for item in items:
        if ":" in item:
            key, value = item.split(":")
            key = key.strip()
            try:
                value = float(value.strip())
            except ValueError:
                value = 0.0
            nutrition[key] = value
    return nutrition


# =========================================================
# 맛 점수 계산
# =========================================================
def calc_taste_score(menu_list):
    score = 0
    for menu in menu_list:
        for kw in TASTY_KEYWORDS:
            if kw in menu:
                score += 2
        for kw in UNTASTY_KEYWORDS:
            if kw in menu:
                score -= 1
    return score


# =========================================================
# 영양소 비율 계산 (다이어트 핵심 기능)
# =========================================================
def calc_nutrition_ratio(nutrition_dict):
    carbo = nutrition_dict.get("탄수화물(g)", 0)
    protein = nutrition_dict.get("단백질(g)", 0)
    fat = nutrition_dict.get("지방(g)", 0)

    carbo_kcal = carbo * 4
    protein_kcal = protein * 4
    fat_kcal = fat * 9
    total = carbo_kcal + protein_kcal + fat_kcal

    if total == 0:
        return {"탄수화물": 0, "단백질": 0, "지방": 0}

    return {
        "탄수화물": round(carbo_kcal / total * 100, 1),
        "단백질": round(protein_kcal / total * 100, 1),
        "지방": round(fat_kcal / total * 100, 1),
    }


# =========================================================
# 계절 판단
# =========================================================
def get_season_by_month(month):
    if month in [3, 4, 5]:
        return "봄"
    elif month in [6, 7, 8]:
        return "여름"
    elif month in [9, 10, 11]:
        return "가을"
    else:
        return "겨울"


@st.cache_data(ttl=86400)
def get_common_menu_by_season(season, sample_start, sample_end):
    all_menus = []
    meals = get_meal_info(
        SCHOOL["시도교육청코드"], SCHOOL["행정표준코드"],
        sample_start, sample_end
    )
    for meal in meals:
        date_obj = datetime.strptime(meal["날짜"], "%Y%m%d")
        if get_season_by_month(date_obj.month) == season:
            all_menus.extend(meal["메뉴"])

    counter = Counter(all_menus)
    return counter.most_common(15)


# =========================================================
# Streamlit UI 구성
# =========================================================
st.title("🍚 당곡고등학교 급식 다이어트 분석기")
st.caption("⚠️ 현재 디버깅 모드로, API 응답이 화면에 그대로 표시됩니다.")

if not API_KEY:
    st.warning("⚠️ NEIS API 키가 설정되지 않았습니다. `.streamlit/secrets.toml`에 NEIS_API_KEY를 추가해주세요.")
    st.stop()

menu = st.sidebar.radio(
    "기능 선택",
    ["1. 영양 비율 계산 (다이어트)", "2. 주간 칼로리 최고/최저", "4. 계절별 인기 반찬"]
)

# ---------------------------------------------------------
# 기능 1: 영양 비율 계산
# ---------------------------------------------------------
if menu == "1. 영양 비율 계산 (다이어트)":
    st.header("📊 영양정보 기반 음식 비율 계산")

    selected_date = st.date_input("날짜 선택", datetime(2025, 5, 14))  # 안전한 과거 날짜 기본값

    if st.button("조회하기"):
        date_str = selected_date.strftime("%Y%m%d")
        meals = get_meal_info(SCHOOL["시도교육청코드"], SCHOOL["행정표준코드"], date_str, date_str)

        if not meals:
            st.info("해당 날짜의 급식 정보가 없습니다. (주말/공휴일이거나 아직 등록되지 않은 급식일 수 있습니다)")
        else:
            for meal in meals:
                st.subheader(f"{meal['식사구분']} (칼로리: {meal['칼로리']} Kcal)")
                st.write("**메뉴:**", ", ".join(meal["메뉴"]))

                ratio = calc_nutrition_ratio(meal["영양정보"])
                df_ratio = pd.DataFrame(
                    {"영양소": list(ratio.keys()), "비율(%)": list(ratio.values())}
                )
                st.bar_chart(df_ratio.set_index("영양소"))
                st.dataframe(df_ratio)

                st.caption(
                    "💡 다이어트 팁: 탄수화물 비율이 60% 이상이면 혈당 스파이크 위험이 있고, "
                    "단백질 비율이 낮으면 근손실 위험이 있습니다."
                )

# ---------------------------------------------------------
# 기능 2: 주간 칼로리 최고/최저
# ---------------------------------------------------------
elif menu == "2. 주간 칼로리 최고/최저":
    st.header("📅 일주일 식단 중 칼로리 최고/최저 날짜")

    start_date = st.date_input("조회 시작일", datetime(2025, 5, 12))
    end_date = st.date_input("조회 종료일", datetime(2025, 5, 16))

    if st.button("분석하기"):
        meals = get_meal_info(
            SCHOOL["시도교육청코드"], SCHOOL["행정표준코드"],
            start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
        )

        if not meals:
            st.info("해당 기간의 급식 정보가 없습니다.")
        else:
            for meal in meals:
                meal["맛점수"] = calc_taste_score(meal["메뉴"])

            df = pd.DataFrame(meals)
            df["메뉴_str"] = df["메뉴"].apply(lambda x: ", ".join(x))

            max_cal_row = df.loc[df["칼로리"].idxmax()]
            min_cal_row = df.loc[df["칼로리"].idxmin()]

            col1, col2 = st.columns(2)
            with col1:
                st.success(f"🔥 가장 칼로리 높은 날: {max_cal_row['날짜']}")
                st.write(f"칼로리: {max_cal_row['칼로리']} Kcal")
                st.write(f"메뉴: {max_cal_row['메뉴_str']}")
                st.write(f"맛 점수: {max_cal_row['맛점수']}")

            with col2:
                st.info(f"🥗 가장 칼로리 낮은 날: {min_cal_row['날짜']}")
                st.write(f"칼로리: {min_cal_row['칼로리']} Kcal")
                st.write(f"메뉴: {min_cal_row['메뉴_str']}")
                st.write(f"맛 점수: {min_cal_row['맛점수']}")

            st.divider()
            st.subheader("전체 급식 목록")
            st.dataframe(df[["날짜", "식사구분", "메뉴_str", "칼로리", "맛점수"]])

            st.caption(
                "⚠️ '맛 점수'는 실제 평가 데이터가 아니라 인기 메뉴 키워드(치킨, 피자 등) 포함 여부로 "
                "임의로 계산한 참고용 지표입니다."
            )

# ---------------------------------------------------------
# 기능 4: 계절별 공통 인기 반찬
# ---------------------------------------------------------
elif menu == "4. 계절별 인기 반찬":
    st.header("🍂 계절별 인기 반찬 (당곡고)")

    season = st.selectbox("계절 선택", ["봄", "여름", "가을", "겨울"])
    year = st.number_input("연도 선택", min_value=2020, max_value=2030, value=2025)

    season_ranges = {
        "봄": (f"{year}0301", f"{year}0531"),
        "여름": (f"{year}0601", f"{year}0831"),
        "가을": (f"{year}0901", f"{year}1130"),
        "겨울": (f"{year}1201", f"{year+1}0228"),
    }

    if st.button("분석 시작"):
        start_date, end_date = season_ranges[season]
        common_menus = get_common_menu_by_season(season, start_date, end_date)

        if not common_menus:
            st.info("해당 계절의 데이터를 찾을 수 없습니다.")
        else:
            df = pd.DataFrame(common_menus, columns=["메뉴", "등장 횟수"])
            st.subheader(f"{season}에 가장 많이 나온 반찬 TOP 15")
            st.dataframe(df)
            st.bar_chart(df.set_index("메뉴"))
