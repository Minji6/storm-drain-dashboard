import folium
import base64
import streamlit as st
from streamlit_folium import st_folium
import streamlit_toggle as tog
from config import gdfs, seocho_dong_geo, load_records
from risk_calc import calculate_risk, rainfall_per_dong

# 침수지도 구분
def flooded_layer(m):
    colors = {"2020": "blue", "2022": "green", "2023": "orange", "2024": "red"}

    # 연도별 레이어 추가
    for year, gdf in gdfs.items():
        if "GU_NAM" in gdf.columns:
            seocho_gdf_subset = gdf[gdf["GU_NAM"] == "서초구"]
            if seocho_gdf_subset.empty:
                print(f"{year} 침수 데이터 내 서초구 데이터 없음")
                continue
            
            folium.GeoJson(
                seocho_gdf_subset,
                name=f"{year} 침수흔적도 서초구 필터링",
                style_function=lambda x, col=colors[year]: {"color": col, "fillOpacity": 0.2, "weight": 1},
                tooltip=folium.GeoJsonTooltip(
                    fields=["F_YR", "F_SHIM", "F_AREA"],
                    aliases=["발생연도", "침수심도(m)", "침수면적(m²)"],
                    localize=True
                ),
                popup=None
            ).add_to(m)

# 행정동명 추출 함수
def extract_dong_name(adm_nm):
    if adm_nm is None:
        return ''
    adm_nm = str(adm_nm).strip()
    # 마지막 단어 (동명)
    return adm_nm.split()[-1]

# 행정동 구분
def boundary_layer(m, risks):
    # 동명 통일
    risks['dong_match'] = risks['dong'].apply(lambda x: extract_dong_name(x))

    # 행정동별 위험도 비율 계산
    dong_stats = (
        risks.groupby('dong_match')["risk_label"]
        .apply(lambda x: (x.isin(["위험", "고위험"]).sum(), len(x)))
        .to_dict()
    )

    # 상태별 개수 통계
    marker_stats = (
        risks.groupby('dong_match')
        .agg(marker_cnt=("dong_match", "count"),
             안전_cnt=("risk_label", lambda x: (x == "안전").sum()),
             관리요망_cnt=("risk_label", lambda x: (x == "관리요망").sum()),
             위험_cnt=("risk_label", lambda x: (x == "위험").sum()),
             고위험_cnt=("risk_label", lambda x: (x == "고위험").sum()))
        .to_dict("index")
    )

    # 밝은 색 매핑 함수
    bright_color_map = {
        
        "#4CAF50": "#7ebc80",
        "#FFC107": "#edddad",
        "#FF9800": "#ecae53",
        "#F44336": "#ec9089"
    }

    def get_color(adm_nm):
        dong_name = extract_dong_name(adm_nm)
        if dong_name not in dong_stats:
            return "lightgray"
        danger_cnt, total_cnt = dong_stats[dong_name]
        ratio = danger_cnt / total_cnt if total_cnt > 0 else 0
        if ratio <= 0.2:
            return "#4CAF50"
        elif ratio <= 0.5:
            return "#FFC107"
        elif ratio <= 0.8:
            return "#FF9800",
        else:
            return "#F44336"

    def get_bright_color(adm_nm):
        base_color = get_color(adm_nm)
        return bright_color_map.get(base_color, "lightgray")

    def highlight_function(feature):
        dong_name = feature["properties"].get("adm_nm", "")
        return {
            "color": "navy",
            "fillColor": get_bright_color(dong_name),
            "weight": 3,
            "opacity": 0.7
        }

    def tooltip_text(feature):
        dong_name = extract_dong_name(feature["properties"].get("adm_nm", ""))
        stats = marker_stats.get(dong_name, {})
        marker_total = stats.get("marker_cnt", 0)
        안전_cnt = stats.get('안전_cnt', 0)
        관리요망_cnt = stats.get('관리요망_cnt', 0)
        위험_cnt = stats.get('위험_cnt', 0)
        고위험_cnt = stats.get('고위험_cnt', 0)
        # 예시: 위험도(%) 임의계산 - 실제 위험도 산식에 맞게 조정 필요
        total = marker_total if marker_total > 0 else 1
        danger_ratio = f"{(위험_cnt / total * 100):.1f} %"

        # 동별 미래 강수 예보 표시
        rain_desc = "강수 데이터 없음"
        if dong_name in rainfall_per_dong:
            rain_series = rainfall_per_dong[dong_name]
            # print(f"[DEBUG] {dong_name} 강수 예보 값:", rain_series)
            rain_sum = rain_series.sum()
            rain_detail = "<br>".join([f"{d}: {v}mm" for d, v in zip(rain_series.index, rain_series.values)])
            rain_desc = f"<b>향후 3일 강수(합):</b> {rain_sum:.1f}mm<br>{rain_detail}"
        else:
            rain_desc = "강수 데이터 없음"

        # 표 형태 HTML 생성
        s = f"""
        <div style="font-family:'맑은 고딕',sans-serif; min-width:200px;">
        <div style="color:#fea51b; font-weight:bold; font-size:15px; margin-bottom:4px;">
            {dong_name}
        </div>
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <tr>
            <td style="border-top:2px solid #233674; font-weight:bold;">빗물받이 개수</td>
            <td style="border-top:2px solid #233674; text-align:right; font-weight:bold;">{marker_total:,} 개</td>
            </tr>
            <tr>
            <td>🟢 안전</td>
            <td style="text-align:right;">{안전_cnt:,} 개</td>
            </tr>
            <tr>
            <td>🟡 관리요망</td>
            <td style="text-align:right;">{관리요망_cnt:,} 개</td>
            </tr>
            <tr>
            <td>🟠 위험</td>
            <td style="text-align:right;">{위험_cnt:,} 개</td>
            </tr>
            <tr>
            <td>🔴 고위험</td>
            <td style="text-align:right;">{고위험_cnt:,} 개</td>
            </tr>
            <tr>
            <td>위험 빗물받이 비율</td>
            <td style="text-align:right;">{danger_ratio}</td>
            </tr>
            <tr>
            <td colspan="2" style="padding-top:8px;">{rain_desc}</td>
            </tr>
        </table>
        </div>
        """
        return s

    # GeoJson feature에 tooltip_html 필드 추가
    for f in seocho_dong_geo["features"]:
        f["properties"]["tooltip_html"] = tooltip_text(f)

    folium.GeoJson(
        seocho_dong_geo,
        name='서초구 행정동 경계',
        style_function=lambda feature: {
            'fillColor': get_color(feature["properties"]["adm_nm"]),
            'color': 'black',
            'weight': 2,
            'fillOpacity': 0.7,
            'opacity': 0.8
        },
        highlight_function=highlight_function,
        zoom_on_click=True,
        tooltip=folium.GeoJsonTooltip(fields=['tooltip_html'], labels=False, style="background-color: white; color: black; font-weight: bold;"),
    ).add_to(m)

def markers(m, risks):
    colors = {
        "안전": "green",
        "관리요망": "orange",
        "위험": "red",
        "고위험": "darkred"
    }
    def image_to_base64(path):
        if not isinstance(path, str) or not path:
            return ""  # 경로가 없거나 숫자면 빈 문자열 반환
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except FileNotFoundError:
            return ""  # 파일이 없으면 빈 문자열 반환

    for _, row in risks.iterrows():
        # 로컬 이미지 경로 사용
        orig_img = row.get('orig_img', '')
        pred_img = row.get('pred_img', '')

        orig_b64 = image_to_base64(orig_img) if orig_img else ""
        pred_b64 = image_to_base64(pred_img) if pred_img else ""

        risk_label = row['risk_label']
        color_emoji = {
            "고위험": "🔴",
            "위험": "🟠",
            "관리요망": "🟡",
            "안전": "🟢"
        }.get(risk_label, "⚪")

        popup_html = f"""
        <b>Risk Label:</b> {color_emoji+" "+risk_label}<br>
        <b>Risk Score:</b> {row['risk_score']:.1f}<br>
        <b>위치:</b> {row['lat']:.5f}, {row['lon']:.5f}<br>
        <b>행정동:</b> {row['dong']}<br>
        <b>점검일:</b> {row['checked_at']}<br>
        <b>상태:</b> {row['state']}<br>
        <table>
            <tr>
                <td>
                    <b>원본사진:</b><br>
                    <img src='data:image/jpeg;base64,{orig_b64}' width='150'>
                </td>
                <td>
                    <b>예측사진:</b><br>
                    <img src='data:image/jpeg;base64,{pred_b64}' width='150'>
                </td>
            </tr>
        </table>
        """

        folium.Marker(
            [row['lat'], row['lon']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row['risk_label'],
            icon=folium.Icon(color=colors.get(row['risk_label'], "blue"), icon="info-sign")
        ).add_to(m)

# 지도 출력
def print_map(risks, key="seocho_map"):
    # 지도 생성
    m = folium.Map(location=[37.477, 127.036], zoom_start=12, tiles="OpenStreetMap")
    boundary_layer(m, risks)

    # 레이어 컨트롤
    folium.LayerControl().add_to(m)

    # Streamlit 출력
    st_data = st_folium(m, width=470, height=500, key=key)
    return st_data

def print_detailed_map():
    records = load_records()
    risks = calculate_risk(records)
    
    flood = tog.st_toggle_switch(label="침수지도", 
                        key="detailed_map_toggle", 
                        default_value=False, 
                        label_after = False, 
                        inactive_color = '#D3D3D3', 
                        active_color="#11567f", 
                        track_color="#29B5E8"
                        )

    # 지도 생성
    m = folium.Map(location=[37.48, 127.01], zoom_start=13, tiles="OpenStreetMap")

    boundary_layer(m, risks)
    
    if flood:
        flooded_layer(m)

    markers(m, risks)

    # 레이어 컨트롤
    folium.LayerControl().add_to(m)

    # Streamlit 출력
    st_folium(m, width=1000, height=600)