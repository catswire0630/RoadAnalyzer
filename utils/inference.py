from ultralytics import YOLO
import cv2
import os
import time
import numpy as np
from utils import yolov8_heatmap
from utils.sort import Sort
from collections import defaultdict
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局模型
detection_model = YOLO("models/best.pt")  # 用于图片和非预警视频
tracking_model = YOLO("models/best.pt")  # 用于预警视频

def _point_in_polygon(point, polygon):
    """判断点是否在多边形内"""
    contour = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    test_point = (int(point[0]), int(point[1]))
    return cv2.pointPolygonTest(contour, test_point, False) >= 0

def _save_keyframe(frame, warning_type, track_id=None, db_path="traffic_data.db", danger_points=None):
    """保存关键帧并记录到数据库"""
    out_path = r"D:\AAbackend\static\warnings"
    os.makedirs(out_path, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{warning_type}_{track_id or 'unknown'}_{timestamp}.jpg"
    filepath = os.path.join(out_path, filename)

    # 绘制危险区域（如果提供）
    if danger_points:
        points_np = np.array(danger_points, dtype=np.int32)
        cv2.polylines(frame, [points_np], isClosed=True, color=(0, 255, 255), thickness=2)

    # 绘制 ID
    if track_id:
        cv2.putText(
            frame,
            f"ID:{track_id} ({warning_type})",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2
        )

    cv2.imwrite(filepath, frame)
    logger.info(f"保存预警帧: {filepath}")

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO warnings (track_id, warning_type, image_path, timestamp) VALUES (?, ?, ?, ?)",
            (track_id, warning_type, f"warnings/{filename}", datetime.now())
        )
        conn.commit()
    return filename

def run_inference(file_path, warning_mode=False):
    try:
        logger.info(f"开始推理: {file_path}, 预警模式: {warning_mode}")
        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")

        if file_path.endswith(('.mp4', '.avi', '.mov')):
            model = tracking_model if warning_mode else detection_model
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                raise ValueError(f"无法打开视频: {file_path}")
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info(f"视频参数: FPS={fps}, 宽={width}, 高={height}")

            # 准备输出视频
            output_dir = "static/annotated/"
            os.makedirs(output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_annotated_{int(time.time())}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if not out.isOpened():
                cap.release()
                raise ValueError(f"无法创建输出视频: {output_path}")

            if not warning_mode:
                # 非预警模式：仅检测
                logger.info("处理视频，非预警模式（仅检测）")
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    results = model(frame, conf=0.5, verbose=False)[0]
                    annotated_frame = results.plot()
                    out.write(annotated_frame)

                cap.release()
                out.release()
                logger.info(f"保存标注视频: {output_path}")

                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise ValueError("标注视频生成失败")

                return {
                    "annotated_video_path": output_path.replace('\\', '/'),
                    "warnings": []
                }

            # 预警模式：跟踪、速度、危险区域、拥堵、行人停留
            logger.info("处理视频，预警模式（启用 SORT 跟踪）")
            image_points = np.array([
                [0, 200], [200, 200], [200, 0], [0, 0]
            ], dtype=np.float32)
            real_world_points = np.array([
                [0, 10], [10, 10], [10, 0], [0, 0]
            ], dtype=np.float32)
            H, _ = cv2.findHomography(image_points, real_world_points)

            danger_region_points = [
                (int(width / 3), int(height / 3)),
                (2 * int(width / 3), int(height / 3)),
                (2 * int(width / 3), 2 * int(height / 3)),
                (int(width / 3), 2 * int(height / 3))
            ]
            danger_region_points_np = np.array(danger_region_points, dtype=np.int32)

            # 初始化 SORT 跟踪器
            tracker = Sort(max_age=1, min_hits=3, iou_threshold=0.3)
            last_positions = {}
            track_history = defaultdict(lambda: {"positions": [], "timestamps": []})
            warnings = []
            speed_limit = 60
            warned_ids = {}
            crowd_threshold = 5
            stop_threshold = 10
            stop_duration = 5

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                results = model(frame, conf=0.5, verbose=False)[0]
                annotated_frame = results.plot()

                cv2.polylines(
                    annotated_frame,
                    [danger_region_points_np],
                    isClosed=True,
                    color=(0, 255, 255),
                    thickness=2
                )

                objects_in_region = 0
                current_time = time.time()

                # 准备 SORT 输入
                detections = []
                classes = []
                for box in results.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = box.conf[0].cpu().numpy()
                    cls_id = int(box.cls[0].cpu().numpy())
                    detections.append([x1, y1, x2, y2, conf])
                    classes.append(cls_id)
                detections = np.array(detections)

                # 更新 SORT 跟踪器
                if len(detections) > 0:
                    tracked_objects = tracker.update(detections)
                else:
                    tracked_objects = tracker.update()

                # 处理跟踪结果
                for obj in tracked_objects:
                    x1, y1, x2, y2, track_id = map(int, obj)
                    x_center = (x1 + x2) / 2
                    y_center = (y1 + y2) / 2
                    box = [x_center, y_center, x2 - x1, y2 - y1]  # xywh

                    # 查找对应的类别（通过 IOU 匹配最近的检测框）
                    iou_scores = []
                    for det in detections:
                        det_x1, det_y1, det_x2, det_y2 = det[:4]
                        iou = max(0, min(x2, det_x2) - max(x1, det_x1)) * max(0, min(y2, det_y2) - max(y1, det_y1))
                        iou /= ((x2 - x1) * (y2 - y1) + (det_x2 - det_x1) * (det_y2 - det_y1) - iou)
                        iou_scores.append(iou)
                    if iou_scores:
                        cls_idx = np.argmax(iou_scores)
                        cls_id = classes[cls_idx]
                        class_name = results.names[cls_id]
                    else:
                        continue  # 跳过无匹配的跟踪对象

                    # 更新轨迹
                    track = track_history[track_id]
                    track["positions"].append((float(x_center), float(y_center)))
                    track["timestamps"].append(current_time)
                    if len(track["positions"]) > 30:
                        track["positions"].pop(0)
                        track["timestamps"].pop(0)

                    # 速度计算
                    pixel_point = np.array([[x_center, y_center]], dtype=np.float32)
                    pixel_point = np.array([pixel_point])
                    real_world_pos = cv2.perspectiveTransform(pixel_point, H)[0][0]
                    speed_kmph = 0
                    if track_id in last_positions:
                        last_x, last_y = last_positions[track_id]
                        dx = real_world_pos[0] - last_x
                        dy = real_world_pos[1] - last_y
                        distance = (dx ** 2 + dy ** 2) ** 0.5
                        speed_mps = distance * fps
                        speed_kmph = speed_mps * 3.6
                    last_positions[track_id] = real_world_pos

                    if class_name == "car":
                        cv2.putText(
                            annotated_frame,
                            f"ID:{track_id} {speed_kmph:.1f} km/h",
                            (int(box[0]), int(box[1] + box[3] + 20)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 0, 0),
                            2
                        )

                    # 危险区域检测
                    in_danger = _point_in_polygon((x_center, y_center), danger_region_points)
                    if in_danger:
                        objects_in_region += 1
                        label = f"ID:{track_id} {class_name} (Danger)"
                        cv2.putText(
                            annotated_frame,
                            label,
                            (int(box[0]), int(box[1] - 50)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 255),
                            2
                        )
                        warning_type = f"{class_name}_in_danger"
                        if (track_id, warning_type) not in warned_ids:
                            filename = _save_keyframe(
                                annotated_frame, warning_type, track_id, danger_points=danger_region_points
                            )
                            warnings.append({
                                "track_id": track_id,
                                "type": warning_type,
                                "message": f"{class_name} ID:{track_id} 进入危险区域",
                                "image_path": f"warnings/{filename}"
                            })
                            warned_ids[(track_id, warning_type)] = True

                    # 超速检测
                    if class_name == "car" and speed_kmph > speed_limit:
                        warning_type = "car_overspeed"
                        if (track_id, warning_type) not in warned_ids:
                            filename = _save_keyframe(
                                annotated_frame, warning_type, track_id, danger_points=danger_region_points
                            )
                            warnings.append({
                                "track_id": track_id,
                                "type": warning_type,
                                "message": f"车辆 ID:{track_id} 超速，速度 {speed_kmph:.1f} km/h",
                                "image_path": f"warnings/{filename}"
                            })
                            warned_ids[(track_id, warning_type)] = True

                    # 行人停留检测
                    if class_name == "person" and len(track["positions"]) >= 2:
                        positions = track["positions"]
                        timestamps = track["timestamps"]
                        if timestamps[-1] - timestamps[0] >= stop_duration:
                            distances = [np.linalg.norm(np.array(positions[i]) - np.array(positions[i-1]))
                                         for i in range(1, len(positions))]
                            avg_distance = np.mean(distances) if distances else float('inf')
                            if avg_distance < stop_threshold and (track_id, "person_stop") not in warned_ids:
                                filename = _save_keyframe(
                                    annotated_frame, "person_stop", track_id, danger_points=danger_region_points
                                )
                                warnings.append({
                                    "track_id": track_id,
                                    "type": "person_stop",
                                    "message": f"行人 ID:{track_id} 长时间停留",
                                    "image_path": f"warnings/{filename}"
                                })
                                warned_ids[(track_id, "person_stop")] = True

                # 拥堵检测
                if objects_in_region >= crowd_threshold:
                    warning_type = "crowd"
                    if ("crowd", current_time) not in warned_ids:
                        filename = _save_keyframe(
                            annotated_frame, warning_type, None, danger_points=danger_region_points
                        )
                        warnings.append({
                            "track_id": None,
                            "type": warning_type,
                            "message": f"区域内 {objects_in_region} 个对象，可能拥堵",
                            "image_path": f"warnings/{filename}"
                        })
                        warned_ids[("crowd", current_time)] = True

                out.write(annotated_frame)

            cap.release()
            out.release()
            logger.info(f"保存标注视频: {output_path}")

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise ValueError("标注视频生成失败")

            return {
                "annotated_video_path": output_path.replace('\\', '/'),
                "warnings": warnings
            }

        elif file_path.endswith(('.jpg', '.jpeg', '.png')):
            model = detection_model
            logger.info("处理图片，禁用跟踪")
            image = cv2.imread(file_path)
            if image is None:
                raise ValueError(f"无法读取图片: {file_path}")
            results = model(image, conf=0.5, verbose=False)[0]
            annotated_image = results.plot()
            annotated_output_dir = "static/annotated/"
            os.makedirs(annotated_output_dir, exist_ok=True)
            base_name = os.path.basename(file_path)
            annotated_filename = f"{os.path.splitext(base_name)[0]}_annotated_{int(time.time())}.jpg"
            annotated_path = os.path.join(annotated_output_dir, annotated_filename)
            if os.path.exists(annotated_path):
                os.remove(annotated_path)
            cv2.imwrite(annotated_path, annotated_image)
            class_counts = {}
            for box in results.boxes:
                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]
                class_counts[class_name] = class_counts.get(class_name, 0) + 1

            heatmap_output_dir = "static/heatmap/"
            os.makedirs(heatmap_output_dir, exist_ok=True)
            temp_dir = os.path.join(heatmap_output_dir, "temp")
            heatmap_filename = f"{os.path.splitext(base_name)[0]}_heatmap_{int(time.time())}.jpg"
            heatmap_path = os.path.join(heatmap_output_dir, heatmap_filename)
            heatmap_model = yolov8_heatmap.yolo_heatmap(**yolov8_heatmap.get_params("models/best.pt"))
            heatmap_model(file_path, temp_dir)
            temp_file = os.path.join(temp_dir, "result.png")
            if os.path.exists(temp_file):
                if os.path.exists(heatmap_path):
                    os.remove(heatmap_path)
                os.rename(temp_file, heatmap_path)
                os.rmdir(temp_dir)
            else:
                os.rmdir(temp_dir)
                heatmap_path = None

            logger.info(f"图片检测完成: 标注路径={annotated_path}, 热力图路径={heatmap_path}")
            return {
                "annotated_image_path": annotated_path.replace('\\', '/'),
                "heatmap_image_path": heatmap_path.replace('\\', '/') if heatmap_path else None,
                "class_counts": class_counts
            }

        else:
            raise ValueError("不支持的文件格式")
    except Exception as e:
        logger.error(f"推理错误: {str(e)}")
        return {"error": str(e)}