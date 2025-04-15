from fastapi import APIRouter, WebSocket
from utils.inference import run_inference
import base64
import cv2
import numpy as np

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 处理实时传输"""
    await websocket.accept()
    while True:
        data = await websocket.receive_text()  # 接收前端传来的图片数据（Base64 编码）
        image_data = base64.b64decode(data)
        np_img = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        results = run_inference(image)  # 运行 YOLO 识别
        await websocket.send_json(results)  # 发送识别结果
