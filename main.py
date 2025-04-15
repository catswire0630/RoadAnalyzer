from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import RedirectResponse
from routes.upload import router as upload_router
from routes.detect import router as detect_router
from routes.websocket import router as websocket_router
from routes.stream import router as stream_router
from fastapi.middleware.cors import CORSMiddleware
import aiohttp
import glob
import os
from typing import Dict
import sqlite3
from datetime import datetime, date
import shutil

app = FastAPI(title="Road Object Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
print(f"静态文件目录: {static_dir}")
if os.path.exists(static_dir):
    print("静态目录存在，文件列表:", os.listdir(static_dir))
else:
    print("静态目录不存在！")
# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/login.html")

@app.get("/warnings")
async def get_warnings():
    db_path = "traffic_data.db"
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM warnings ORDER BY timestamp DESC")
            warnings = cursor.fetchall()
            return [{
                "id": w["id"],
                "track_id": w["track_id"],
                "warning_type": w["warning_type"],
                "image_path": w["image_path"],
                "timestamp": w["timestamp"]
            } for w in warnings]
    except Exception as e:
        print(f"获取警告错误: {e}")
        return {"error": str(e)}

@app.delete("/warnings")
async def clear_warnings():
    db_path = "traffic_data.db"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM warnings")
            conn.commit()

        warnings_dir = r"D:\AAbackend\static\warnings"
        if os.path.exists(warnings_dir):
            for file in os.listdir(warnings_dir):
                file_path = os.path.join(warnings_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        return {"success": True}
    except Exception as e:
        print(f"清空警告错误: {e}")
        return {"success": False, "error": str(e)}

# 注册路由
app.include_router(upload_router)
app.include_router(detect_router)
app.include_router(stream_router)
app.include_router(websocket_router)

@app.get("/history")
async def get_history():
    db_path = "traffic_data.db"
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM detections ORDER BY timestamp DESC")
            records = cursor.fetchall()
            return [{
                "id": r["id"],
                "filename": r["filename"],
                "timestamp": r["timestamp"],
                "type": r["type"]
            } for r in records]
    except Exception as e:
        print(f"历史记录错误: {e}")
        return {"error": str(e)}

@app.post("/traffic-qa")
async def traffic_qa(data: Dict[str, str]):
    question = data.get("question")
    if not question:
        return JSONResponse(status_code=400, content={"error": "问题不能为空"})

    async with aiohttp.ClientSession() as session:
        payload = {
            "model": "traffic2",
            "prompt": question,
            "stream": False
        }
        async with session.post("http://localhost:11434/api/generate", json=payload) as response:
            if response.status != 200:
                return JSONResponse(status_code=500, content={"error": "模型推理失败"})
            result = await response.json()
            answer = result.get("response", "无法生成回答")

            db_path = "traffic_data.db"
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO qa_records (question, timestamp) VALUES (?, datetime('now'))",
                        (question,)
                    )
                    conn.commit()
            except Exception as e:
                print(f"记录问答错误: {e}")

            return {"answer": answer}

@app.get("/dashboard")
async def get_dashboard():
    db_path = "traffic_data.db"
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM detections")
            total_detections = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM detections WHERE date(timestamp) = ?", (today_str,))
            daily_detections = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM warnings")
            total_warnings = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM warnings WHERE date(timestamp) = ?", (today_str,))
            daily_warnings = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM qa_records")
            total_qa = cursor.fetchone()[0]

            return {
                "total_detections": total_detections,
                "daily_detections": daily_detections,
                "total_warnings": total_warnings,
                "daily_warnings": daily_warnings,
                "total_qa": total_qa
            }
    except Exception as e:
        print(f"仪表板错误: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)