import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime, timedelta
import requests
import math

from config import SERVICE_KEY, DAILY_URL, STATIONS_CSV, gdfs

def recency_score(dt, ref_date=None):
    if pd.isna(dt): return 1.0
    if ref_date is None: ref_date = datetime.now()
    days = (ref_date - dt).days
    if days <= 7: return 0.0
    elif days <= 30: return 0.2
    elif days <= 90: return 0.5
    elif days <= 365: return 0.8
    else: return 1.0

# gdf_points 계산
def cal_gdf(records):
    gdf_points = gpd.GeoDataFrame(records, geometry=[Point(xy) for xy in zip(records['lon'], records['lat'])],
                                    crs="EPSG:4326")
    
    # H 계산 (침수 흔적 여부: 있으면 1, 없으면 0)
    gdf_points["H"] = 0
    for year, flood_gdf  in gdfs.items():
        if not isinstance(flood_gdf, gpd.GeoDataFrame):
            print(f"[경고] {year} flood_gdf 타입:", type(flood_gdf))
            continue

        joined = gpd.sjoin(gdf_points, flood_gdf, how="left", predicate="within")
        gdf_points["H"] |= joined.index_right.notnull().astype(int)

    # S 계산
    state_map = {"grid_0":0.0,"grid_1":0.50,"grid_2":1.00,"grid_cover":1.00}
    gdf_points['S'] = gdf_points['state'].map(state_map).fillna(0.2)

    # R 계산
    gdf_points['R'] = gdf_points['checked_at'].apply(lambda d: recency_score(d))

    return gdf_points

# P 계산
def compute_P_from_series(daily_series):
    A = daily_series.sum()
    if A == 0: return 0.0
    elif A < 20: return 0.1
    elif A < 50: return 0.5
    elif A < 100: return 0.85
    else: return 1.0

# 기상청 예보 API 관련 함수
def fetch_forecast_rain(row):
    def get_latest_base_time_and_date():
        now = datetime.now()
        time_slots = [2, 5, 8, 11, 14, 17, 20, 23]
        hour = now.hour
        base_time_hour = max([t for t in time_slots if t <= hour], default=23)
        base_time = f"{base_time_hour:02d}00"
        base_date = now.strftime("%Y%m%d")
        if hour < 2:
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        return base_date, base_time
    
    base_date, base_time = get_latest_base_time_and_date()

    # lat/lon → nx/ny
    def latlon_to_xy(lat, lon):
        RE = 6371.00877 # 지구 반경(km)
        GRID = 5.0      # 격자 간격(km)
        SLAT1 = 30.0    # 표준위도1
        SLAT2 = 60.0    # 표준위도2
        OLON = 126.0    # 기준점 경도
        OLAT = 38.0     # 기준점 위도
        XO = 43         # 기준점 X좌표
        YO = 136        # 기준점 Y좌표

        DEGRAD = math.pi / 180.0
        re = RE / GRID
        slat1 = SLAT1 * DEGRAD
        slat2 = SLAT2 * DEGRAD
        olon = OLON * DEGRAD
        olat = OLAT * DEGRAD

        sn = math.tan(math.pi*0.25 + slat2*0.5) / math.tan(math.pi*0.25 + slat1*0.5)
        sn = math.log(math.cos(slat1)/math.cos(slat2)) / math.log(sn)
        sf = math.tan(math.pi*0.25 + slat1*0.5)
        sf = math.pow(sf, sn) * math.cos(slat1) / sn
        ro = math.tan(math.pi*0.25 + olat*0.5)
        ro = re * sf / math.pow(ro, sn)
        ra = math.tan(math.pi*0.25 + lat*DEGRAD*0.5)
        ra = re * sf / math.pow(ra, sn)
        theta = lon*DEGRAD - olon
        if theta > math.pi: theta -= 2.0*math.pi
        if theta < -math.pi: theta += 2.0*math.pi
        theta *= sn
        x = int(ra*math.sin(theta) + XO + 0.5)
        y = int(ro - ra*math.cos(theta) + YO + 0.5)
        return x, y

    nx, ny = latlon_to_xy(row["lat"], row["lon"])
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "1000",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }

    resp = requests.get(DAILY_URL, params=params)
    print("API Response:", resp.text[:300])  # 앞 500글자만 출력
    data = resp.json()

    if "response" in data and data["response"]["header"]["resultCode"] != "00":
        print(f"API Error for {row['dong']}: {data['response']['header']['resultMsg']}")
        return pd.Series([0, 0, 0],
                         index=[datetime.now().date() + timedelta(days=i) for i in range(1, 4)])

    items = data["response"]["body"]["items"]["item"]

    # print("base:", base_date, base_time, "nx,ny:", nx, ny)
    # print("item count:", len(items))
    # print("categories:", sorted({i.get("category") for i in items}))

    # PCP(강수량) 만 추출
    pcp_items = [i for i in items if i["category"] == "PCP"]
    df = pd.DataFrame(pcp_items)

    # print("RN1 rows:", len(rn1_items))
    # if rn1_items[:3]:
    #     print("RN1 sample:", rn1_items[:3])

    # 문자열 처리: "강수없음" → 0.0, 나머지는 float 변환
    def parse_pcp_value(val):
        if val in ["강수없음", "-", ""]:
            return 0.0
        if "1mm 미만" in str(val):
            return 0.5
        if "30.0~50.0mm" in str(val):
            return 40.0
        if "50.0mm이상" in str(val):
            return 100.0
        val_str = str(val).strip()
        if val_str.endswith("mm"):
            try:
                return float(val_str.replace("mm", ""))
            except ValueError:
                print(f"Unexpected PCP value: {val}")
                return 0.0
        try:
            return float(val)
        except ValueError:
            print(f"Unexpected PCP value: {val}")
            return 0.0

    if df.empty:
        # PCP 데이터가 아예 없을 때
        today = datetime.now().date()
        return pd.Series([0, 0, 0], index=[today + timedelta(days=i) for i in range(1, 4)])

    df['fcstDateTime'] = pd.to_datetime(df['fcstDate'] + df['fcstTime'], format="%Y%m%d%H%M")
    df['pcpValue'] = df['fcstValue'].apply(parse_pcp_value)
    df['date'] = df['fcstDateTime'].dt.date

    # 날짜별 강수량 합계 (1일/3일 단위)
    daily_rain = df.groupby('date')['pcpValue'].sum()

    today = datetime.now().date()
    future_3days = [today + timedelta(days=i) for i in range(1, 4)]
    return daily_rain.reindex(future_3days, fill_value=0)

# ----------------------------
# 동별 관측소 매핑
# ----------------------------
stations = pd.read_csv(STATIONS_CSV)

# ----------------------------
# 위험도 계산
# ----------------------------

def risk_label_from_score(r):
    if r<=40: return "안전"
    elif r<=60: return "관리요망"
    elif r<=80: return "위험"
    else: return "고위험"

rainfall_per_dong = {}
for _, row in stations.iterrows():
    dong = row['dong']
    try:
        daily_series = fetch_forecast_rain(row)
        rainfall_per_dong[dong] = daily_series
    except Exception as e:
        print(f"Error fetching rain data for {dong}: {e}")
        rainfall_per_dong[dong] = pd.Series([0,0,0], index=[datetime.now().date() + timedelta(days=i) for i in range(1,4)])

# 2) calculate_risk 함수 내에서는 API 호출 대신 딕셔너리에서 데이터 참조
def calculate_risk(records):
    w_hist,w_state,w_recency,w_rain=0.20,0.40,0.20,0.30
    
    # 최신 checked_at 기준으로 정렬 후 (lat, lon) 중복 제거 → 최신만 남김
    records = records.sort_values("checked_at", ascending=False)\
                     .drop_duplicates(subset=["lat", "lon"], keep="first")
    gdf_points = cal_gdf(records)

    results = []
    for _, row in gdf_points.iterrows():
        try:
            H, S, R = row['H'], row['S'], row['R']
            dong = row['dong']
            if dong in rainfall_per_dong:
                daily_series = rainfall_per_dong[dong]
                P = compute_P_from_series(daily_series)
            else:
                # P = 0.85  # 호우
                P = 1.0  # 폭우
            r = 100 * (w_hist*H + w_state*S + w_recency*R + w_rain*P)
            label = risk_label_from_score(r)
            results.append({"lat": row['lat'],
                            "lon": row['lon'],
                            "dong": dong,
                             "state": row['state'],
                             "orig_img": row['orig_img'],
                             "pred_img": row['pred_img'],
                             "checked_at": row['checked_at'],
                            "risk_score": round(r, 2), "risk_label": label})
            
        except Exception as e:
            results.append({"lat": row['lat'], "lon": row['lon'], "dong": dong,
                            "state": row['state'], "orig_img": row['orig_img'], "pred_img": row['pred_img'], "checked_at": row['checked_at'],
                            "risk_score": None, "risk_label": "error"})
            print("row error:", e)
    return pd.DataFrame(results)
