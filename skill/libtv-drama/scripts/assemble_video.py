#!/usr/bin/env python3
# assemble_video.py — 把分镜图本地拼成竖屏 MP4（非会员账号视频算力不足时的兜底）
# 依赖：Pillow, imageio, imageio-ffmpeg（venv 需预装）
# 用法：DUR=10 python assemble_video.py <项目目录>
#   项目目录需含 assets/shotN.png（N 从 1 起，连续）；可选 quote.txt 作缺失镜兜底金句卡。
# 产物：<项目目录>/drama_final.mp4  （1080x1920, 含轻微推镜+交叉淡入）

import os, sys, glob, textwrap
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import imageio.v2 as imageio

PROJ = sys.argv[1] if len(sys.argv) > 1 else "."
ASSETS = os.path.join(PROJ, "assets")
OUT = os.path.join(PROJ, "drama_final.mp4")
DUR = float(os.environ.get("DUR", "10"))
FPS = 24
W, H = 1080, 1920
CROSS = 6  # 交叉淡入帧数
ZOOM = 0.06  # 推镜幅度


def find_font():
    cands = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]
    for f in cands:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, 64)
            except Exception:
                pass
    return ImageFont.load_default()


def fit(img, scale):
    iw, ih = img.size
    nw, nh = int(iw * scale), int(ih * scale)
    res = img.resize((nw, nh), Image.LANCZOS)
    # 居中裁到目标
    left = (nw - W) // 2 if nw >= W else 0
    top = (nh - H) // 2 if nh >= H else 0
    if nw >= W and nh >= H:
        return res.crop((left, top, left + W, top + H))
    # 小于目标则先扩白底再贴
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(res, (max(0, (W - nw) // 2), max(0, (H - nh) // 2)))
    return canvas


def fallback_card(text):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    font = find_font()
    lines = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, 12) or [""]
    lh = 80
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) / 2, y), ln, fill=(255, 255, 255), font=font)
        y += lh
    return img


def shot_frames(img, nframes):
    out = []
    denom = max(1, nframes - 1)
    for k in range(nframes):
        s = 1.0 + ZOOM * (k / denom)
        out.append(fit(img, s))
    return out


def main():
    # 决定期望镜头号
    shots = []
    st = os.path.join(PROJ, "shots.txt")
    if os.path.exists(st):
        with open(st, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                num = line.split("\t", 1)[0].strip()
                if num.isdigit():
                    shots.append(int(num))
    if not shots:
        shots = sorted(
            int(os.path.basename(p).split("shot")[1].split(".")[0])
            for p in glob.glob(os.path.join(ASSETS, "shot*.png"))
        )
    if not shots:
        print("[assemble] ERROR: 未找到任何分镜图/镜头号", file=sys.stderr)
        sys.exit(1)

    quote = ""
    qf = os.path.join(PROJ, "quote.txt")
    if os.path.exists(qf):
        quote = open(qf, encoding="utf-8").read().strip()

    per = max(1, int(round(DUR / len(shots) * FPS)))
    allf = []
    for idx, num in enumerate(shots):
        path = os.path.join(ASSETS, f"shot{num}.png")
        if os.path.exists(path):
            img = Image.open(path).convert("RGB")
            fr = shot_frames(img, per)
        else:
            print(f"[assemble] shot {num} 缺失，用金句卡兜底", file=sys.stderr)
            fr = shot_frames(fallback_card(quote or f"（第 {num} 镜缺失）"), per)
        # 交叉淡入
        if not allf:
            allf = fr
        else:
            X = min(CROSS, len(allf), len(fr))
            blended = [
                Image.blend(allf[len(allf) - X + j], fr[j], (j + 1) / (X + 1))
                for j in range(X)
            ]
            allf = allf[:-X] + blended + fr[X:]

    writer = imageio.get_writer(
        OUT, fps=FPS, codec="libx264", quality=8,
        pixelformat="yuv420p", macro_block_size=1,
    )
    for fr in allf:
        writer.append_data(np.asarray(fr))
    writer.close()
    print(f"[assemble] OK -> {OUT}  ({len(allf)} frames, {len(shots)} shots)")


if __name__ == "__main__":
    main()
