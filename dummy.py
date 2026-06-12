import random
import csv
from datetime import datetime, timedelta
import geopandas as gpd
from shapely.geometry import Point

# 1. 서울 행정동 경계 geojson 파일 로드
gdf = gpd.read_file('./data/서울_행정동_경계_2017.geojson')

# 서초구 필터링
gdf_seocho = gdf[gdf['adm_nm'].str.contains('서초구')].copy()

# 좌표계 변환
if gdf_seocho.crs != 'EPSG:4326':
    gdf_seocho = gdf_seocho.to_crs(epsg=4326)

# 2. 위도/경도 생성 함수
def random_point_in_bbox(min_lat, min_lon, max_lat, max_lon):
    lat = random.uniform(min_lat, max_lat)
    lon = random.uniform(min_lon, max_lon)
    return lat, lon

# 3. 좌표로 행정동 찾기
def find_adm_nm(lat, lon, gdf):
    point = Point(lon, lat)
    match = gdf[gdf.geometry.contains(point)]
    if len(match) > 0:
        return match.iloc[0]['adm_nm']
    else:
        return None

# 4. dummy 데이터 생성
status_choices = ['grid_0', 'grid_1', 'grid_2', 'grid_cover']
weights = [2, 1, 1, 1]

start_date = datetime(2024, 9, 1)
end_date = datetime.now()

num_points = 200   # 랜덤 위치 개수
rows = []

# 서초구 대략 bbox
min_lat, max_lat = 37.45, 37.53
min_lon, max_lon = 126.97, 127.06

unique_points = []

# 200개의 랜덤 좌표 확보
while len(unique_points) < num_points:
    lat, lon = random_point_in_bbox(min_lat, min_lon, max_lat, max_lon)
    adm_nm = find_adm_nm(lat, lon, gdf_seocho)
    if adm_nm and "서초구" in adm_nm:
        dong_name = adm_nm.split()[-1]
        point = (round(lat, 6), round(lon, 6), dong_name)
        if point not in unique_points:
            unique_points.append(point)

# 각 좌표마다 5개 데이터 생성
for lat, lon, dong_name in unique_points:
    for i in range(5):
        status = random.choices(status_choices, weights=weights, k=1)[0]
        original_path = None
        predicted_path = None

        # ✅ start_date ~ end_date 사이에서 랜덤 날짜 생성
        total_seconds = int((end_date - start_date).total_seconds())
        rand_seconds = random.randint(0, total_seconds)
        checkdate = (start_date + timedelta(seconds=rand_seconds)).strftime('%Y-%m-%d %H:%M:%S')

        rows.append([lat, lon, dong_name, status, original_path, predicted_path, checkdate])

# 5. CSV 저장
with open('./results/records.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['위도(x)', '경도(y)', '행정동', '상태', '원본 경로', '예측 경로', '점검일'])
    writer.writerows(rows)

print(f"생성된 데이터 개수: {len(rows)}")  # 1000 확인용
