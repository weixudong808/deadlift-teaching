#!/usr/bin/env python3
"""scan_video.py — 用MediaPipe扫描硬拉视频, 输出膝角/髋角/腕高曲线, 定位动作阶段.

用法: python3 scan_video.py <视频> [步长秒, 默认0.5]
输出: JSON数组 stdout (重定向落盘再读). 腕高=杠高代理, y越小杠越高.
选段纪律见 references/fullrep-gif-pipeline.md: 粗扫0.5s看结构, 细扫0.25s定起止.
"""
import sys, json, os
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision as mp_vision

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pose_landmarker_full.task")

def ang3(a, b, c):
    v1, v2 = a - b, c - b
    cosv = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cosv, -1, 1))))

def main():
    src, step = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS)
    det = mp_vision.PoseLandmarker.create_from_options(
        mp_vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=MODEL),
            running_mode=mp_vision.RunningMode.IMAGE, num_poses=1))
    rows = []
    t = 0.0
    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        frame = frame[: h - h % 4, : w - w % 4]
        res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                  data=np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))))
        if res.pose_landmarks:
            lm = res.pose_landmarks[0]
            g = lambda i: np.array([lm[i].x * w, lm[i].y * h])
            knee = ang3(g(23), g(25), g(27))          # 髋-膝-踝
            hip = ang3(g(11), g(23), g(25))           # 肩-髋-膝
            wr_y = (lm[15].y + lm[16].y) / 2          # 腕(杠)高度 0=顶 1=底
            sh_y = (lm[11].y + lm[12].y) / 2
            rows.append({"t": round(t, 1), "knee": round(knee), "hip": round(hip),
                         "bar_y": round(wr_y, 2), "sh_y": round(sh_y, 2)})
        else:
            rows.append({"t": round(t, 1), "no_pose": True})
        t += step
    det.close()
    cap.release()
    print(json.dumps(rows, ensure_ascii=False))

if __name__ == "__main__":
    main()
