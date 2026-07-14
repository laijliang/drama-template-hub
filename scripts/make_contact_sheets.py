# coding=utf-8
"""
把已抽好的帧拼成分组 contact sheet（拉片分析用）。

读 frames/ 下的 frame_XXXX_ttt.sss.jpg，按场景切换分组，每组拼一张网格图，
每格标时间戳+帧号、场景切换帧加红框，输出到 contact_sheets/，并打印 manifest 片段。

设计要点（和方案一致）：
- 单张拼图长边 ≤ --max-long（默认 1536），避免被多模态模型降采样吃掉细节
- 每张默认 12 帧，列行/缩略图按帧实际宽高比自适应（横屏/竖屏都行）
- 分界吸附到最近的场景切换帧，让一张图尽量对应完整镜头段
- 零新增依赖（PIL / cv2 / numpy 运行时已装，这里只用 PIL）

用法:
  python scripts/make_contact_sheets.py <frames_dir> [--manifest m.json]
      [--per-sheet 12] [--max-long 1536] [--scene-threshold 28] [--out DIR]
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FRAME_RE = re.compile(r"frame_(\d+)_([\d.]+)s\.jpg$", re.I)


def load_frames(frames_dir: Path) -> list:
    items = []
    for p in sorted(frames_dir.glob("*.jpg")):
        m = FRAME_RE.search(p.name)
        if not m:
            continue
        items.append({"path": p, "index": int(m.group(1)), "time": float(m.group(2))})
    items.sort(key=lambda x: x["index"])
    return items


def load_scene_flags(manifest_path, scene_threshold: float) -> set:
    """从 manifest 的 frame_extraction.frames[].scene_score 找出场景切换帧 index。"""
    flags = set()
    if not manifest_path:
        return flags
    try:
        data = json.load(open(manifest_path, encoding="utf-8"))
        for fr in data.get("frame_extraction", {}).get("frames", []) or []:
            if float(fr.get("scene_score", 0) or 0) >= scene_threshold:
                flags.add(int(fr.get("index", -1)))
    except Exception:
        pass
    return flags


def group_frames(items: list, per_sheet: int, scene_set: set) -> list:
    """均分为 N 组，分界吸附到最近的场景切换帧（窗口内），不把一个镜头劈成两张。"""
    n = len(items)
    groups_n = max(1, math.ceil(n / per_sheet))
    ideal = [round(i * n / groups_n) for i in range(1, groups_n)]
    scene_pos = [i for i, it in enumerate(items) if it["index"] in scene_set]
    win = max(1, per_sheet // 2)
    bounds = []
    for b in ideal:
        best = b
        if scene_pos:
            cand = min(scene_pos, key=lambda p: abs(p - b))
            if abs(cand - b) <= win:
                best = cand
        bounds.append(best)
    bounds = sorted(set([0] + bounds + [n]))
    groups = []
    for i in range(len(bounds) - 1):
        seg = items[bounds[i]:bounds[i + 1]]
        if seg:
            groups.append(seg)
    return groups


def choose_grid(n: int, ar: float, max_long: int, min_cols: int = 2):
    """在长边 ≤ max_long 的约束下，选让每格面积最大的列行布局（自然平衡接近方形）。"""
    best = None
    for cols in range(min(min_cols, n), n + 1):
        rows = math.ceil(n / cols)
        sheet_ar = (cols * ar) / rows  # 宽/高
        if sheet_ar >= 1:
            tw = max_long / cols
            th = tw / ar
        else:
            th = max_long / rows
            tw = th * ar
        area = tw * th
        if best is None or area > best[0]:
            best = (area, cols, rows, int(round(tw)), int(round(th)))
    return best[1], best[2], best[3], best[4]


def load_font(px: int):
    try:
        return ImageFont.load_default(size=max(13, px))
    except TypeError:
        return ImageFont.load_default()


def build_sheet(group, cols, rows, tw, th, scene_set, gap=4, bg=(18, 22, 28)):
    W = cols * tw + (cols + 1) * gap
    H = rows * th + (rows + 1) * gap
    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)
    font = load_font(th // 13)
    for k, it in enumerate(group):
        r, c = divmod(k, cols)
        x = gap + c * (tw + gap)
        y = gap + r * (th + gap)
        try:
            im = Image.open(it["path"]).convert("RGB").resize((tw, th), Image.LANCZOS)
        except Exception:
            continue
        canvas.paste(im, (x, y))
        is_cut = it["index"] in scene_set
        if is_cut:
            draw.rectangle([x, y, x + tw - 1, y + th - 1], outline=(235, 64, 52), width=3)
        label = f"{it['time']:.1f}s #{it['index']}" + ("  CUT" if is_cut else "")
        tb = draw.textbbox((0, 0), label, font=font)
        lw, lh = tb[2] - tb[0], tb[3] - tb[1]
        draw.rectangle([x, y, x + lw + 8, y + lh + 6], fill=(0, 0, 0))
        draw.text((x + 4, y + 2), label, fill=(255, 220, 90) if is_cut else (255, 255, 255), font=font)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--per-sheet", type=int, default=12)
    ap.add_argument("--max-long", type=int, default=1536)
    ap.add_argument("--scene-threshold", type=float, default=28.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quality", type=int, default=88)
    args = ap.parse_args()

    frames_dir = Path(args.frames_dir)
    items = load_frames(frames_dir)
    if not items:
        print(json.dumps({"error": "no frames found", "frames_dir": str(frames_dir)}, ensure_ascii=False))
        return

    default_manifest = frames_dir.parent / "manifest.json"
    manifest = args.manifest or (str(default_manifest) if default_manifest.exists() else None)
    scene_set = load_scene_flags(manifest, args.scene_threshold)

    with Image.open(items[0]["path"]) as im0:
        fw, fh = im0.size
    ar = fw / fh

    groups = group_frames(items, args.per_sheet, scene_set)
    out_dir = Path(args.out) if args.out else (frames_dir.parent / "contact_sheets")
    out_dir.mkdir(parents=True, exist_ok=True)

    sheets = []
    for gi, group in enumerate(groups):
        cols, rows, tw, th = choose_grid(len(group), ar, args.max_long)
        sheet = build_sheet(group, cols, rows, tw, th, scene_set)
        fname = f"sheet_{gi:02d}.jpg"
        sheet.save(out_dir / fname, quality=args.quality)
        sheets.append({
            "file": f"{out_dir.name}/{fname}",
            "grid": [cols, rows],
            "size": list(sheet.size),
            "frames": [group[0]["index"], group[-1]["index"]],
            "time_range": [round(group[0]["time"], 2), round(group[-1]["time"], 2)],
            "cells": [
                {"index": it["index"], "time": round(it["time"], 2), "scene_change": it["index"] in scene_set}
                for it in group
            ],
        })

    result = {
        "frames_dir": str(frames_dir),
        "out_dir": str(out_dir),
        "frame_count": len(items),
        "sheet_count": len(sheets),
        "per_sheet": args.per_sheet,
        "aspect": round(ar, 3),
        "orientation": "landscape" if ar >= 1 else "portrait",
        "scene_change_frames": sorted(scene_set),
        "contact_sheets": sheets,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
