from fastapi import APIRouter, HTTPException, Query
import sqlite3
from utils.inference import run_inference
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/detect/{filename}")
async def detect_file(
    filename: str,
    warning_mode: bool = Query(False, description="是否启用预警模式")
):
    file_path = f"static/uploads/{filename}"
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        raise HTTPException(status_code=404, detail="文件不存在")
    logger.info(f"开始检测: {file_path}, 预警模式: {warning_mode}")
    try:
        result = run_inference(file_path, warning_mode=warning_mode)
        if "error" in result:
            logger.error(f"检测失败: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        db_path = "traffic_data.db"
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            detection_type = "video" if file_path.endswith(('.mp4', '.avi', '.mov')) else "image"
            cursor.execute(
                """
                INSERT INTO detections (filename, type, timestamp)
                VALUES (?, ?, datetime('now'))
                """,
                (filename, detection_type)
            )
            conn.commit()
            logger.info(f"记录检测: {detection_type}, 文件名: {filename}")
        return result
    except Exception as e:
        logger.error(f"检测异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")