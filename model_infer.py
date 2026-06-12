import os
from ultralytics import YOLO
from PIL import Image
import streamlit as st
from data_utils import get_lat_lon, save_record, find_adm_nm

best_weight = "./yolov11_seg/best.pt"
model = YOLO(best_weight)

# 모델 예측
def run_inference(img_path, uploaded_file):
    results = model.predict(source=img_path, save=False, device="cuda:0", conf=0.5)
    result = results[0]

    # 원본/예측 이미지 저장 경로
    original_path = f"./results/images/original/{uploaded_file.name}"
    predicted_path = f"./results/images/predicted/result_{uploaded_file.name}"

    # 원본 저장
    with open(original_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # 예측 결과 저장
    result.save(filename=predicted_path)

    # 상태(가장 많이 나온 클래스명 or 미검출)
    label_counts = {}
    for box in result.boxes:
        cls_id = int(box.cls[0])
        label = model.names[cls_id]
        label_counts[label] = label_counts.get(label, 0) + 1

    status = max(label_counts, key=label_counts.get) if label_counts else "미검출"

    return predicted_path, status, label_counts, original_path


# 이미지 업로드
def image_upload():

    uploaded_file = st.file_uploader("이미지를 업로드하세요", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        st.image(uploaded_file, caption="업로드된 원본 이미지", width=500)

        if st.button("예측 실행"):
            temp_file = f"./temp_{uploaded_file.name}"
            with open(temp_file, "wb") as f:
                f.write(uploaded_file.getbuffer())

            try:
                # 모델 예측 실행
                predicted_path, status, label_counts, original_path = run_inference(temp_file, uploaded_file)

                # 예측 결과 출력
                st.image(Image.open(predicted_path), caption="YOLO 예측 결과", width=500)
                st.subheader("검출된 객체")
                st.json(label_counts)

                # 위도/경도 추출
                latitude, longitude = get_lat_lon(original_path)

                if latitude is None or longitude is None:
                    st.warning("⚠️ 이 이미지에는 GPS(위도/경도) 정보가 존재하지 않습니다.")
                    latitude, longitude = "", ""  # CSV에는 빈칸 저장
                else:
                    st.success(f"GPS 정보 감지됨 → 위도: {latitude:.6f}, 경도: {longitude:.6f}")

                # 행정동 찾기
                adm_dong = find_adm_nm(latitude, longitude)

                st.write(f"해당 위치 행정동: {adm_dong}")

                # 데이터 저장
                save_record(latitude, longitude, adm_dong, status, original_path, predicted_path, temp_file)

                st.success("데이터가 ./results/records.csv 에 저장되었습니다.")

                # 임시파일 정리
                os.remove(temp_file)

            except Exception as e:
                st.error(f"예측 중 오류 발생: {e}")