import os
import pandas as pd
import json
import geopandas as gpd
from dotenv import load_dotenv

load_dotenv()

########################## 행정동 데이터 관리 ##########################

# GeoJSON 파일 로드 (행정동 경계 데이터)
with open('./data/서울_행정동_경계_2017.geojson', 'r', encoding='utf-8') as f:
    dong_geo = json.load(f)

# 서초구의 행정동만 필터링
seocho_dongs = []
for feature in dong_geo['features']:
    if '서초구' in feature['properties']['adm_nm']:
        seocho_dongs.append(feature)

# 서초구 행정동만 포함하는 새로운 GeoJSON 생성
seocho_dong_geo = {
    "type": "FeatureCollection",
    "features": seocho_dongs
}

# 서초구 필터링 GeoJSON (dict)를 GeoDataFrame으로 변환
seocho_gdf = gpd.GeoDataFrame.from_features(seocho_dong_geo["features"])
# 좌표계 WGS84로 통일
if seocho_gdf.crs != 'EPSG:4326':
    seocho_gdf = seocho_gdf.set_crs(epsg=4326, allow_override=True)

########################## 침수지도 데이터 관련 ##########################

# 침수지도 불러오기
gdfs = {
    "2020": gpd.read_file("./data/2020년 서울특별시 침수흔적도/서울시_2020.shp").to_crs(epsg=4326),
    "2022": gpd.read_file("./data/2022년 침수흔적도_230717수정/서울시_2022.shp").to_crs(epsg=4326),
    "2023": gpd.read_file("./data/2023년 서울특별시 침수흔적도/2023_서울시_침수흔적도.shp").to_crs(epsg=4326),
    "2024": gpd.read_file("./data/2024년 서울특별시 침수흔적도/2024_서울시_침수흔적도.shp").to_crs(epsg=4326)
}

########################## 날씨 데이터 관련 ##########################

SERVICE_KEY = os.environ["KMA_SERVICE_KEY"]
DAILY_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
STATIONS_CSV = "./data/stations_meta.csv"
RECORDS_PATH = "./results/records.csv"

# 빗물받이데이터 불러오기
def load_records():
    records= pd.read_csv(RECORDS_PATH, header=0,
                        names=["lat","lon","dong","state","orig_img","pred_img","checked_at"])
    
    records['checked_at'] = pd.to_datetime(records['checked_at'], errors='coerce')
    
    return records