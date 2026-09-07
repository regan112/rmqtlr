python
복사
import requests

API_KEY = "여기에_본인의_API_키_입력"  # secrets.toml에 넣은 키와 동일하게

url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
params = {
    "KEY": API_KEY,
    "Type": "json",
    "pIndex": 1,
    "pSize": 100,
    "ATPT_OFC_CODE": "B10",
    "SD_SCHUL_CODE": "7010073",  # 당곡고
    "MLSV_FROM_YMD": "20250301",
    "MLSV_TO_YMD": "20250331",
}

res = requests.get(url, params=params)
print("상태 코드:", res.status_code)
print("응답 원문:")
print(res.text)
