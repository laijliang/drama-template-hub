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
    """顺序切分为每组 ≤ per_sheet 帧，分界尽量吸附到场景切换帧，不把一个镜头劈成两张。

    分界必须「顺序推进」：从上一个分界出发，理想分界 = 上一分界 + per_sheet，
    只在 [理想-win, 理想] 这个「向前回看」的窗口里找切换点。这样在数学上保证
    每组不超过 per_sheet（旧实现让每个分界各自独立吸附到最近切换点，相邻分界会
    撞到同一点被去重合并成超大组、或相向靠拢挤出 3~4 帧的碎片组）。
    """
    n = len(items)
    if n <= per_sheet:
        return [items]
    scene_pos = sorted(i for i, it in enumerate(items) if it["index"] in scene_set)
    win = max(1, per_sheet // 3)              # 吸附窗口：只向前回看，保证不超上限
    min_size = max(2, (per_sheet + 1) // 2)   # 最小组长，避免碎片组
    bounds = [0]
    while n - bounds[-1] > per_sheet:
        start = bounds[-1]
        ideal = start + per_sheet
        cands = [p for p in scene_pos
                 if ideal - win <= p <= ideal and p - start >= min_size]
        bounds.append(max(cands) if cands else ideal)
    bounds.append(n)
    groups = [items[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]
    # 处理过小的尾组：能并回前一组就并；并了会超上限就把两组重新均分，
    # 避免出现只有 1~2 帧的碎片尾图
    if len(groups) >= 2 and len(groups[-1]) < min_size:
        merged = groups[-2] + groups[-1]
        if len(merged) <= per_sheet:
            groups[-2] = merged
            groups.pop()
        else:
            half = (len(merged) + 1) // 2
            groups[-2], groups[-1] = merged[:half], merged[half:]
    return [g for g in groups if g]


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

    # 网格按 per_sheet 算一次、全片统一：每格尺寸恒定，所有拼图版式一致
    # （旧实现按每组实际帧数各算各的，导致同一部片出现 3x4/4x2/3x7 等多种版式）
    cols, rows, tw, th = choose_grid(args.per_sheet, ar, args.max_long)

    sheets = []
    for gi, group in enumerate(groups):
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
