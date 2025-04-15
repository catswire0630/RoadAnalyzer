from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import cv2
from ultralytics import YOLO
import time

router = APIRouter()
model = YOLO("models/best.pt")


def generate_frames():
    # 使用摄像头（0 为默认摄像头，可改为视频文件路径）
    cap = cv2.VideoCapture(0)  # 或 "path/to/video.mp4"
    if not cap.isOpened():
        raise ValueError("无法打开视频源")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 使用 YOLO 检测
            results = model(frame)[0]
            annotated_frame = results.plot()  # 带标注的帧

            # 转换为 JPEG
            ret, buffer = cv2.imencode('.jpg', annotated_frame)
            frame_bytes = buffer.tobytes()

            # MJPEG 流格式
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            # 控制帧率（可选）
            time.sleep(0.033)  # 约 30 FPS
    finally:
        cap.release()


@router.get("/stream")
async def video_stream():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")