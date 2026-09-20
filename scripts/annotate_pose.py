#!/usr/bin/env python3
"""annotate_pose.py — 硬拉教学图关节标注 (deadlift-teaching v1, 2026-09-19)

教学照片 -> MediaPipe关键点 -> 骨架连线+关节圆点+动作要点标签.
与 form-analysis 模式A 的区别: 不做基准对比打分, 只画骨架+标要点 (教学用).

Usage: python3 annotate_pose.py <img1.jpg> [img2.jpg ...] <outdir>
位置·视角从文件名解析: 01_start_front.jpg -> start_front (front/side + start/mid/top/lower)
标签从内置 LABELS 取; 文件名不带合法位置则只画骨架不贴标签.
"""
import os, sys, re, json
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "pose_landmarker_full.task")
FONT_PATH = "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc"

GREEN = (40, 200, 90)
DARK = (25, 25, 25)
WHITE = (255, 255, 255)

# MediaPipe Pose 索引
NOSE = 0; LEAR = 7; REAR = 8
LSH, RSH = 11, 12; LEL, REL = 13, 14; LWR, RWR = 15, 16
LHIP, RHIP = 23, 24; LKNEE, RKNEE = 25, 26; LANK, RANK = 27, 28

BONES_ALL = [
    (7, 11), (8, 12),                     # 耳-肩 (仅侧面画, 正面会擦过脸颊)
    (11, 13), (13, 15), (12, 14), (14, 16),  # 双臂
    (11, 12), (23, 24),                   # 肩线 / 髋线
    (11, 23), (12, 24),                   # 躯干
    (23, 25), (25, 27), (24, 26), (26, 28),  # 双腿
]
BONES_FRONT = [b for b in BONES_ALL if b not in ((7, 11), (8, 12))]
JOINTS = [LEAR, REAR, LSH, RSH, LEL, REL, LWR, RWR,
          LHIP, RHIP, LKNEE, RKNEE, LANK, RANK]

# 图上标签: 位置_key -> [(文字, 锚点关节列表取中点, y偏移(图高比例, 负=向上))]
LABELS = {
    "start_front": [("握距略宽于肩√", [LWR, RWR], -0.06), ("小腿贴杠√", [LANK, RANK], -0.07)],
    "start_side":  [("背保持平√", [LSH, LHIP], 0.0), ("眼看前地面√", [NOSE], -0.07), ("杠压脚中√", [LANK], -0.06)],
    "mid_front":   [("杠过膝√", [LWR, RWR], -0.05), ("膝对脚尖√", [LKNEE, RKNEE], -0.07)],
    "mid_side":    [("杠过膝√", [LWR, RWR], -0.05), ("背仍平√", [LSH, LHIP], 0.0)],
    "top_front":   [("髋膝伸直√", [LKNEE, RKNEE], -0.07), ("肩在杠正上√", [LSH, RSH], -0.07)],
    "top_side":    [("杠贴大腿√", [LWR, RWR], -0.04), ("屁股夹紧√", [LHIP], -0.07)],
    "lower_hip_side":   [("第1拍: 先屈髋√", [LHIP], -0.07), ("膝先稳住√", [LKNEE], -0.07)],
    "lower_knee_side":  [("第2拍: 再屈膝√", [LKNEE, RKNEE], -0.08), ("杠贴腿滑√", [LWR, RWR], -0.05)],
}


def mp_ready(img_bgr):
    """宽/高补到4的倍数, 防分割mask core dump (继承自旧skill实测教训)."""
    h, w = img_bgr.shape[:2]
    return img_bgr[: h - h % 4, : w - w % 4].copy()


def parse_key(name):
    m = re.search(r"(front|side)", name, re.I), re.search(
        r"(start|mid|top|lower_hip|lower_knee|lower)", name, re.I)
    if not all(m):
        return None
    view = "front" if m[0].group().lower() == "front" else "side"
    pos = m[1].group().lower()
    return f"{pos}_{view}"


def detect_view(lm, W):
    """左右肩x间距占图宽比例: 正面大/侧面小."""
    dx = abs(lm[LSH][0] - lm[RSH][0]) * W
    return "front" if dx > 0.12 * W else "side"


def ang3(a, b, c):
    a, b, c = np.asarray(a, float), np.asarray(b, float), np.asarray(c, float)
    v1, v2 = a - b, c - b
    cosv = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cosv, -1, 1))))


def crop_black_bars(img_bgr, thresh=16):
    """裁掉截图式黑边 (07/08原图自带, 教学拼图尺寸统一)."""
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    rows = np.where(g.max(axis=1) > thresh)[0]
    cols = np.where(g.max(axis=0) > thresh)[0]
    if len(rows) == 0 or len(cols) == 0:
        return img_bgr
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    if y0 > 8 or (g.shape[0] - y1) > 8 or x0 > 8 or (g.shape[1] - x1) > 8:
        return img_bgr[y0:y1, x0:x1]
    return img_bgr


def draw_annotated(img_bgr, key, pts, W, H, out_path, view="side"):
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil, "RGBA")
    lw = max(4, W // 170)
    f_tag = ImageFont.truetype(FONT_PATH, max(20, W // 26))

    # 骨架: 先深色描边再亮色实线 (浅背景/深背景都可读); 正面不画耳-肩线(擦脸)
    bones = BONES_FRONT if view == "front" else BONES_ALL
    for a, b in bones:
        pa, pb = pts[a], pts[b]
        d.line([tuple(pa), tuple(pb)], fill=DARK + (160,), width=lw + 4)
        d.line([tuple(pa), tuple(pb)], fill=GREEN + (255,), width=lw)
    for j in JOINTS:
        r = max(5, lw)
        x, y = pts[j]
        d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE + (255,),
                  outline=GREEN + (255,), width=max(2, lw // 2))

    # 要点标签
    for txt, anchors, dy in LABELS.get(key, []):
        ax = np.mean([pts[i][0] for i in anchors])
        ay = np.mean([pts[i][1] for i in anchors]) + dy * H
        tw, th = d.textbbox((0, 0), txt, font=f_tag)[2:]
        x = min(max(8, ax - tw / 2), W - tw - 8)
        y = min(max(8, ay), H - th - 8)
        d.rounded_rectangle([x - 10, y - 6, x + tw + 10, y + th + 6],
                            radius=8, fill=DARK + (185,))
        d.text((x, y), txt, font=f_tag, fill=(160, 255, 180, 255))

    pil.save(out_path, quality=90)
    return out_path


def analyze(path, det, outdir):
    name = os.path.basename(path)
    key = parse_key(name)
    img = cv2.imread(path)
    if img is None:
        return {"img": name, "error": "图片读取失败"}
    img = mp_ready(img)
    img = crop_black_bars(img)
    H, W = img.shape[:2]
    res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                              data=np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))))
    if not res.pose_landmarks:
        return {"img": name, "error": "未检测到人体"}
    lm = [(l.x, l.y, float(getattr(l, "visibility", 1.0)))
          for l in res.pose_landmarks[0]]
    pts = {i: np.array([lm[i][0] * W, lm[i][1] * H]) for i in range(33)}

    v_auto = detect_view(lm, W)
    warn = None
    if key:
        want = "front" if key.endswith("front") else "side"
        if want != v_auto:
            warn = f"文件名标注{want}但自动判断{v_auto}, 标签按文件名走"
    knee_a = ang3(pts[LHIP], pts[LKNEE], pts[LANK])
    out = {"img": name, "key": key, "view_auto": v_auto, "knee_angle": round(knee_a, 1)}
    if warn:
        out["warn"] = warn
    out_path = os.path.join(outdir, "ann_" + os.path.splitext(name)[0] + ".jpg")
    out["annotated"] = draw_annotated(img, key, pts, W, H, out_path,
                                      view="front" if key and key.endswith("front") else "side")
    return out


def main():
    *IMGS, OUT = sys.argv[1:]
    os.makedirs(OUT, exist_ok=True)
    det = mp_vision.PoseLandmarker.create_from_options(
        mp_vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=MODEL),
            running_mode=mp_vision.RunningMode.IMAGE, num_poses=1))
    results = [analyze(p, det, OUT) for p in IMGS]
    det.close()
    print(json.dumps({"results": results}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
