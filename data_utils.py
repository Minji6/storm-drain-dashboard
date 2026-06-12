import os
import csv
import datetime
from shapely.geometry import Point
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from config import seocho_gdf, RECORDS_PATH

# 이미지 -> 데이터
def save_record(latitude, longitude, adm_dong, status, original_path, predicted_path, img_path):
    # 점검일 = 업로드된 파일 생성 날짜
    ctime = os.path.getctime(img_path)
    check_date = datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")

    file_exists = os.path.exists(RECORDS_PATH)

    with open(RECORDS_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:  # 헤더 없으면 추가
            writer.writerow(["위도(x)", "경도(y)", "행정동", "상태", "원본 경로", "예측 경로", "점검일"])
        writer.writerow([latitude, longitude, adm_dong, status, original_path, predicted_path, check_date])

# 위/경도 추출
def get_lat_lon(img_path):
    def get_exif_data(img_path):
        image = Image.open(img_path)
        exif_data = {}
        info = image._getexif()
        if not info:
            return None
        
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]
                exif_data["GPSInfo"] = gps_data
            else:
                exif_data[decoded] = value
        return exif_data

    def convert_to_degrees(value):
        def rational_to_float(x):
            # IFDRational이나 tuple 모두 처리
            if hasattr(x, "numerator") and hasattr(x, "denominator"):
                return float(x.numerator) / float(x.denominator)
            elif isinstance(x, tuple) and len(x) == 2:
                return float(x[0]) / float(x[1])
            else:
                return float(x)

        d = rational_to_float(value[0])
        m = rational_to_float(value[1])
        s = rational_to_float(value[2])

        return d + (m / 60.0) + (s / 3600.0)
    
    exif_data = get_exif_data(img_path)
    if not exif_data or "GPSInfo" not in exif_data:
        return None, None

    gps_info = exif_data["GPSInfo"]

    lat = convert_to_degrees(gps_info["GPSLatitude"])
    if gps_info["GPSLatitudeRef"] != "N":
        lat = -lat

    lon = convert_to_degrees(gps_info["GPSLongitude"])
    if gps_info["GPSLongitudeRef"] != "E":
        lon = -lon

    return lat, lon

# 행정동 찾기
def find_adm_nm(lat, lon):
    point = Point(lon, lat)
    match = seocho_gdf[seocho_gdf.geometry.contains(point)]
    if len(match) > 0:
        adm_nm = match.iloc[0]['adm_nm']
        return adm_nm.split()[-1]  # 행정동명만 리턴
    else:
        return ''