#!/usr/bin/env python3
"""make_fullrep_gifs.py — 从正面/侧面视频各挑一次完整硬拉(拉起→下落)生成GIF.

选段依据见 references/fullrep-gif-pipeline.md (0.25s细扫腕高曲线人工确认):
  侧面 B_091817: 15.0s地面预备 -> 16.75s锁定 -> 18.5s放回地面, 取 15.0-19.0s
  正面 C_54d7:   12.0s地面     -> 13.75s锁定 -> 16.75s放回地面, 取 12.0-17.2s (17.25后松手)
复用: 改顶部 JOBS 的视频路径/时间戳/文字即可, 其他不用动.
风格与 09-19 lowering.gif 一致: 顶部提示条 + 右下角帧序徽章 (教练认可).
v2: fit_font()字号自适应防裁切; 相邻帧去重(顶部落定段删冗余); 宽320控制体积.
"""
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc"
VID_B = "/root/.hermes/cache/documents/doc_906999b0a5ea_VID_20260916_091817.mp4"
VID_C = "/root/.hermes/cache/documents/doc_54d7ef756e9f_18446744073456285039.mp4"
OUTDIR = "/tmp/dl-teach"

JOBS = [
    # (视频, t0, t1, 帧间隔s, 输出宽, 提示文字, 输出名)
    (VID_B, 15.0, 19.0, 0.15, 320, "侧面观 · 完整硬拉：拉起 → 下落", "fullrep_side.gif"),
    (VID_C, 12.0, 17.2, 0.15, 320, "正面观 · 完整硬拉：拉起 → 下落", "fullrep_front.gif"),
]


def extract(src, t0, t1, step, tw):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames, times = [], []
    t = t0
    while t < t1 - 1e-6:
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * fps))
        ok, fr = cap.read()
        if not ok:
            break
        h, w = fr.shape[:2]
        fr = cv2.resize(fr, (tw, int(tw * h / w)))
        frames.append(fr)
        times.append(t)
        t += step
    cap.release()
    return frames, times


def dedupe(frames, thr=3.0):
    """相邻帧平均绝对差<thr 则丢弃(删除顶部落定段的冗余帧)."""
    kept = [frames[0]]
    for f in frames[1:]:
        if np.abs(f.astype(int) - kept[-1].astype(int)).mean() >= thr:
            kept.append(f)
    return kept


def fit_font(d, txt, max_w, start=24):
    size = start
    while size > 12:
        f = ImageFont.truetype(FONT, size)
        if d.textbbox((0, 0), txt, font=f)[2] <= max_w:
            return f
        size -= 1
    return ImageFont.truetype(FONT, 12)


def make_gif(frames, txt, out_path):
    pil_frames = []
    for i, fr in enumerate(frames):
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(im, "RGBA")
        f = fit_font(d, txt, im.width - 16)
        twd, thd = d.textbbox((0, 0), txt, font=f)[2:]
        d.rectangle([0, 0, im.width, thd + 26], fill=(20, 20, 20, 165))
        d.text(((im.width - twd) / 2, 13), txt, font=f, fill=(255, 255, 255, 255))
        # 帧序徽章
        f2 = ImageFont.truetype(FONT, 16)
        d.rectangle([im.width - 46, im.height - 34, im.width, im.height],
                    fill=(20, 20, 20, 150))
        d.text((im.width - 35, im.height - 30), f"{i+1:02d}", font=f2,
               fill=(255, 255, 255, 230))
        pil_frames.append(im)
    pil_frames[0].save(out_path, save_all=True, append_images=pil_frames[1:],
                       duration=150, loop=0, optimize=True)
    return len(pil_frames), os.path.getsize(out_path) // 1024


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    for src, t0, t1, step, tw, txt, name in JOBS:
        frames, times = extract(src, t0, t1, step, tw)
        n_raw = len(frames)
        frames = dedupe(frames)
        out = os.path.join(OUTDIR, name)
        n, kb = make_gif(frames, txt, out)
        print(f"{name}: {n_raw}帧去重后{n}帧 {kb}KB  时间{t0}-{t1}s")
