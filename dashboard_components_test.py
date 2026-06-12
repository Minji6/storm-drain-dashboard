import pandas as pd
import altair as alt
import streamlit as st
import plotly.graph_objects as go
from shapely.geometry import Point, shape
from map_view import print_map, extract_dong_name
from risk_calc import calculate_risk
from config import load_records, seocho_dong_geo

def get_status_color(label):
    """상태별 고유 색상 반환"""
    color_map = {
        "안전": "#4CAF50",
        "관리요망": "#FFC107",
        "위험": "#FF9800",
        "고위험": "#F44336"
    }
    return color_map.get(label, "#999999")

def create_summary_cards(risks):
    """4개 위험도 상태(안전, 관리요망, 위험, 고위험) 별 합계 카드 생성"""
    total_count = len(risks)
    high_risk_count = len(risks[risks['risk_label'] == "고위험"])
    warning_count = len(risks[risks['risk_label'] == "위험"])
    manage_count = len(risks[risks['risk_label'] == "관리요망"])
    safe_count = len(risks[risks['risk_label'] == "안전"])

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📊 전체 빗물받이", f"{total_count:,}개")
    with col2:
        percentage = f"{(high_risk_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        st.metric("🔴 고위험", f"{high_risk_count:,}개", percentage)
    with col3:
        percentage = f"{(warning_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        st.metric("🟠 위험", f"{warning_count:,}개", percentage)
    with col4:
        percentage = f"{(manage_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        st.metric("🟡 관리요망", f"{manage_count:,}개", percentage)
    with col5:
        percentage = f"{(safe_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        st.metric("🟢 안전", f"{safe_count:,}개", percentage)

def create_calculation_info():
    # 위험도 계산 방식 설명
    with st.expander("🧮 위험도 계산 방식", expanded=False):
        st.markdown("""
        **위험도 점수 = 100 × (H×0.20 + S×0.40 + R×0.20 + P×0.30)**
        
        - **H (History)**: 과거 침수 이력 (0/1)
        - **S (State)**: 현재 시설 상태 (0-1)
          - 안전: 0.15 | 관리요망: 0.40 | 고위험: 1.00 | 덮개상태: 1.00
        - **R (Recency)**: 점검 최근성 (0-1)
          - 7일: 0.0 | 30일: 0.2 | 90일: 0.5 | 1년: 0.8 | 1년+: 1.0
        - **P (Precipitation)**: 강수량 예측 (0-1)
          - 20mm: 0.1 | 50mm: 0.5 | 100mm: 0.85 | 100mm+: 1.0
        """)

def create_top_risk_table(risks):
    """risk 결과의 위험도 상위 5개 빗물받이 테이블 생성"""
    top_risk = risks.nlargest(5, 'risk_score').reset_index(drop=True)

    st.markdown("#### 위험도 상위 빗물받이")
    st.markdown("""
    **위험도 기준**
    - 🔴 **80점 이상**: 고위험
    - 🟠 **60-80점**: 위험  
    - 🟡 **40-60점**: 관리요망  
    - 🟢 **40점 미만**: 안전
    ---    
    """)

    for idx, row in top_risk.iterrows():
        rank = idx + 1
        location = f"{row['dong']} {row['lat']:.3f}, {row['lon']:.2f}"
        risk_score = int(row['risk_score']) if pd.notna(row['risk_score']) else 0
        risk_label = row.get('risk_label', '알수없음')

        color_emoji = {
            "고위험": "🔴",
            "위험": "🟠",
            "관리요망": "🟡",
            "안전": "🟢"
        }.get(risk_label, "⚪")

        col1, col2, col3 = st.columns([1, 2, 1], gap="small")
        with col1:
            st.write(f"**{rank}** {color_emoji}")
        with col2:
            st.write(location)
        with col3:
            st.write(f"**{risk_score}**")
                # 범례 표시

def create_district_status(risks):
    """18개 행정동 상태별 퍼센트(안전, 관리요망, 위험, 고위험) 차트 생성"""
    # 행정동별 위험 상태 분포 집계
    district_status_counts = risks.groupby(['dong', 'risk_label']).size().unstack(fill_value=0)
    district_status_percents = district_status_counts.div(district_status_counts.sum(axis=1), axis=0) * 100
    district_status_percents = district_status_percents.fillna(0)

    districts = list(district_status_percents.index)
    labels = ["안전", "관리요망", "위험", "고위험"]

    # 상태별 색상 리스트
    colors = [get_status_color(lab) for lab in labels]

    # 각 상태별 퍼센트 값 가져오기, 없는 컬럼은 0으로 채움
    data_traces = []
    for label, color in zip(labels, colors):
        vals = district_status_percents[label] if label in district_status_percents.columns else [0]*len(districts)
        text_vals = [f"{v:.1f}%" if v > 0 else "" for v in vals]
        trace = go.Bar(
            y=districts,
            x=vals,
            name=label,
            orientation='h',
            marker=dict(color=color),
            text=text_vals,
            textposition='inside',
            textfont=dict(color='black', size=12, family='Arial Black'),
            hovertemplate='%{x:.1f}%<extra></extra>'
        )
        data_traces.append(trace)

    fig = go.Figure(data=data_traces)
    fig.update_layout(
        barmode='stack',
        title=dict(text="행정동별 현재 위험도 상태 분포 (%)", font=dict(size=18)),
        xaxis=dict(
            title='퍼센트 (%)',
            range=[0, 100],
            ticksuffix='%',
            color='white',
            gridcolor='rgba(200,200,200,0.2)'
        ),
        yaxis=dict(title="행정동", color='white'),
        height=500,
        width=800,
        legend_title_text="상태",
        legend=dict(font=dict(color='white')),
        plot_bgcolor='black',
        paper_bgcolor='black',
        margin=dict(l=120, r=40, t=50, b=50)
    )
    st.plotly_chart(fig, use_container_width=True)

def get_dong_from_coords(lat, lng):
    point = Point(lng, lat)  # shapely는 (x, y) = (lon, lat)
    for feature in seocho_dong_geo["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            return extract_dong_name(feature["properties"].get("adm_nm"))
    return None

def create_dong_graph(records, dong_name):
    # 특정 행정동 + 상태 필터
    subset = records[
        records["dong"].str.contains(dong_name, na=False) &
        records["state"].isin(["grid_2", "grid_cover"])
    ].copy()

    if subset.empty:
        st.warning(f"'{dong_name}' 행정동에 막힘/덮힘 데이터가 없습니다.")
        return

    # 상태 이름 변경
    subset["state"] = subset["state"].map({"grid_2": "막힘", "grid_cover": "덮힘"})

    # 고유 빗물받이 식별자
    subset["id"] = subset["lat"].astype(str) + "_" + subset["lon"].astype(str)

    # 월 단위 생성
    subset["month"] = subset["checked_at"].dt.to_period("M")

    # 최근 12개월 범위 (이번 달 기준)
    end = pd.Timestamp.now().to_period("M")
    months = pd.period_range(end=end, periods=12, freq="M")

    # 모든 id x month 조합 생성
    all_combinations = pd.MultiIndex.from_product([subset["id"].unique(), months], names=["id", "month"]).to_frame(index=False)

    # 기존 데이터와 병합하여 최신 상태 forward-fill
    subset_sorted = subset.sort_values(["id", "month"])
    merged = pd.merge(all_combinations, subset_sorted[["id", "month", "state"]], on=["id", "month"], how="left")
    merged = merged.sort_values(["id", "month"])
    merged["state"] = merged.groupby("id")["state"].ffill().fillna("None")  # 초기 값 없으면 None 처리

    # 월별 상태별 개수 집계
    monthly_counts = merged.groupby(["month", "state"]).size().unstack(fill_value=0)
    # 막힘/덮힘 컬럼이 없는 경우 대비
    for col in ["막힘", "덮힘"]:
        if col not in monthly_counts.columns:
            monthly_counts[col] = 0
    monthly_counts = monthly_counts[["막힘", "덮힘"]].reset_index()
    monthly_counts["month"] = monthly_counts["month"].dt.strftime("%m월")

    # Altair용 long 형태
    df_long = monthly_counts.melt(id_vars="month", var_name="state", value_name="count")

    # Altair 차트 생성
    chart = (
        alt.Chart(df_long)
        .mark_bar()
        .encode(
            x=alt.X("month:N", title="월", sort=[m.to_timestamp().strftime("%m월") for m in months]),
            y=alt.Y("count:Q", title="개수"),
            color=alt.Color(
                "state:N",
                title="상태",
                scale=alt.Scale(domain=["막힘", "덮힘"], range=["#FF6B6B", "#4ECDC4"])
            ),
            tooltip=["month", "state", "count"]
        )
        .properties(width=700, height=400, title="행정동 빗물받이 상태 변화 [최근 12개월]")
    )

    st.altair_chart(chart, use_container_width=True)

def display_dashboard():
    records = load_records()
    risks = calculate_risk(records)

    create_summary_cards(risks)
    create_calculation_info()

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        map_data = print_map(risks, key="seocho_map")
    with col2:
        clicked_dong = None
        if map_data and "last_clicked" in map_data:
            coords = map_data["last_clicked"]
            if coords:
                lat, lng = coords["lat"], coords["lng"]
                clicked_dong = get_dong_from_coords(lat, lng)

        if clicked_dong:
            st.subheader(f"{clicked_dong}")
            create_dong_graph(records, clicked_dong)
        else:
            st.info("지도에서 행정동(폴리곤)을 클릭하면 해당 동의 그래프가 표시됩니다.")

    col3, col4 = st.columns([1, 1])
    with col3:
        create_top_risk_table(risks)
    with col4:
        create_district_status(risks)