import os
import streamlit as st
from streamlit_option_menu import option_menu

from model_infer import image_upload
from map_view import print_detailed_map
from dashboard_components_test import display_dashboard

# 사이드바
def side_bar():
    with st.sidebar:
        # option_menu를 사용해 사이드바 메뉴 생성
        tabs = option_menu(
            menu_title=None,
            options=['종합현황', '지역 상세 관리', '이미지 업로드', '설정'],
            icons=['bar-chart-fill', 'search', 'image', 'gear'],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#111"},
                "icon": {"color": "#fff", "font-size": "20px"},
                "nav-link": {
                    "color": "#818181",
                    "font-size": "18px",
                    "text-align": "left",
                    "margin": "10px",
                    "transition": ".3s",
                },
                "nav-link-selected": {"background-color": "#02ab21", "color": "white"},
            },
        )

    if tabs == '종합현황':
        st.subheader("📊 종합현황")
        display_dashboard()

    elif tabs == '지역 상세 관리':
        st.subheader("🔍 지역 상세 관리")
        print_detailed_map()

    elif tabs == '이미지 업로드':
        st.subheader("🖼️ 이미지 업로드")
        image_upload()

        if st.button("닫기"):
            st.session_state["show_modal"] = False

        st.markdown("</div></div>", unsafe_allow_html=True)

    elif tabs == '설정':
        st.subheader("설정")
        # st.write(f"Name of option is {tabs}")


# 바텀바
def bottom_bar():
    # 페이지 하단
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>빗물받이 관리 서비스 v1.0</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(page_title="빗물받이 관리 서비스", layout="wide", page_icon="🌧️")
    
    st.title("빗물받이 관리 서비스")
    
    # st.markdown('<style>' + open('./style.css').read() + '</style>', unsafe_allow_html=True)

    # 데이터 저장 디렉토리
    os.makedirs("./results/images/original", exist_ok=True)
    os.makedirs("./results/images/predicted", exist_ok=True)

    side_bar()
    bottom_bar()