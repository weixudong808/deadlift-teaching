---
name: deadlift-teaching
description: "硬拉教学标准输出。触发：用户说'教我做硬拉/教我硬拉/硬拉怎么练（要教学）'→ 直接发成品三件套（4步教学长图 + 正面/侧面完整硬拉动图），零计算不重新生成；教练给新照片/视频时才用脚本重新生成。与 form-analysis(纠错分析)分工：本skill做'教'，不做'评'。v1.0.0 已定稿（2026-09-20 小卫验收通过）。"
metadata:
  version: 1.0.0
  tags: [fitness, deadlift, teaching, gif, mediapipe, tutorial]
---

# 硬拉教学（deadlift-teaching）

> ✅ **v1.0.0 定稿**（2026-09-20 小卫验收通过，原话："以后只要说教我做硬拉，就按着这个输出就行"）。改版需求先改本文件再动工。

## 标准输出（默认路径，直接发成品，零计算）

用户说"教我做硬拉"→ 按顺序发三件套：

1. `MEDIA:/root/.hermes/skills/deadlift-teaching/assets/fullrep_front.gif` — 正面观·完整硬拉动图
2. `MEDIA:/root/.hermes/skills/deadlift-teaching/assets/fullrep_side.gif` — 侧面观·完整硬拉动图
3. `MEDIA:/root/.hermes/skills/deadlift-teaching/assets/tutorial_v2.png` — 四步教学长图（1080x5109）

配一句简短引导语（按该会员 profile.style）。动图在前先看动作全程，长图在后细看每步要点。

## 产出规格

用户说"教我怎么做硬拉"时输出：
1. **四步教学长图**（templates/tutorial.html 渲染 PNG）：①起始位 ②中间位 ③站立位 ④下落位（每步正面+侧面标注图 + 要点）+ **⑤完整动作演示**（正/侧 GIF 并排区）+ 金句/新手三大坑页脚。①-④ 是教练已认可内容，**改版不许动**。
2. **正面 + 侧面完整硬拉动图**各一条：一次完整 rep（地面→拉起→锁定→下落回地面）。小卫明确要求：**不压缩整段视频，只挑一次完整硬拉**。规格：宽320、150ms/帧循环、顶部提示条+帧序徽章、单条 ≤3.5MB。

## 标注图管线

`scripts/annotate_pose.py <img...> <outdir>`：教学照 → MediaPipe 关键点 → 骨架连线 + 关节圆点 + 要点标签。文件名解析位置视角（如 `01_start_front.jpg`→start_front），标签取自内置 LABELS；文件名无合法位置则只画骨架。与 form-analysis 的区别：不做基准对比打分，只画骨架+标要点。

## 动图选段与生成（必读 references/fullrep-gif-pipeline.md）

1. **找落盘视频**：`~/.hermes/cache/documents/doc_*.mp4`，先 md5sum 去重（同视频多副本）。
2. **两步扫描选 rep**：`scripts/scan_video.py <视频> <步长s>` 输出膝角/髋角/腕高(=杠高)曲线。粗扫 0.5s 看结构 → 细扫 0.25s 定起止。**起止以扫描曲线为准**——缩略图墙+vision 只当假设，实测 vision 臆造过"18-21s 慢放"（实际 17.5→18.5s 一秒放完）。
3. **生成**：`scripts/make_fullrep_gifs.py`（顶部 JOBS 改时间戳/源即可复用）。规格：宽320、步长0.15s、相邻帧去重(差<3.0)、顶部提示条+帧序徽章、单条 ≤3.5MB。
4. **长图渲染**：`chromium-browser`（无 `chromium`）--headless --window-size=1080,6000 → 按内容行裁底（背景浅灰，别用"灰度>20"判断）。

## 红线 / 踩坑速记（详见参考文件）

- 中文横幅 ≈ 字号像素宽，窄画面必裁 → 用 fit_font() 自适应缩号
- 人物松手后腕高假性回升，那是收尾不是下落，选段掐掉（C 案例 17.25s）
- 语音消息同音字："夏洛"= 下落；按上下文猜健身术语，别按字面搜
- 标注图文字禁 emoji（用 √/×）；MediaPipe 输入 4 字节对齐
- 会话自带 vision_analyze 429 无权限，一律用 mcp_zai_vision_mcp_analyze_image

## 文件索引

| 文件 | 内容 |
|---|---|
| `assets/tutorial_v2.png` | 成品长图（直接发） |
| `assets/fullrep_front.gif` / `fullrep_side.gif` | 成品动图（直接发） |
| `assets/annotated/*.jpg` | 8 张步骤标注照（重渲染依赖，勿删） |
| `references/fullrep-gif-pipeline.md` | 动图管线完整记录：素材表、选段数据、GIF 规格、踩坑、待办 |
| `scripts/annotate_pose.py` | 教学照骨架标注（模型 `scripts/pose_landmarker_full.task` 同目录加载，缺失即崩） |
| `scripts/scan_video.py` | 姿态扫描输出动作曲线 |
| `scripts/make_fullrep_gifs.py` | 完整 rep GIF 生成（OUTDIR=/tmp/dl-teach 临时产物） |
| `templates/tutorial.html` | 四步长图模板（相对路径指向 `../assets/`；改后用 chromium-browser 重渲染并覆盖 `assets/tutorial_v2.png`） |
