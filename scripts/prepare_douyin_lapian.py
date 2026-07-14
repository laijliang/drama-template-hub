# coding=utf-8
"""
Prepare Douyin video assets for shot-by-shot analysis.

Usage:
  python scripts/prepare_douyin_lapian.py "<douyin url>"

Output:
  A local mp4, extracted frames, and a manifest JSON under Output/media/<video_id>/.
"""
import argparse
import concurrent.futures
import json
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import cv2
    import requests
    from dotenv import load_dotenv
except ModuleNotFoundError as e:
    missing = e.name or str(e)
    print(json.dumps({
        "error": "missing_dependency",
        "message": f"缺少 Python 依赖: {missing}",
        "install": "python -m pip install opencv-python-headless requests python-dotenv",
    }, ensure_ascii=False, indent=2))
    sys.exit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "Output" / "media"

sys.path.insert(0, str(SCRIPT_DIR))
from get_douyin_video import SPIDER_PATH, extract_video_info, load_env, normalize_douyin_url


def safe_name(value: str, fallback: str = "douyin_video") -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", value or "").strip(" ._")
    return value[:80] or fallback


def get_video_info(source_url: str) -> dict:
    resolved_url = normalize_douyin_url(source_url)
    load_dotenv(SPIDER_PATH / ".env")
    auth = load_env()
    info = extract_video_info(auth, resolved_url)
    if info.get("error"):
        raise RuntimeError(json.dumps(info, ensure_ascii=False))
    info["source_url"] = source_url
    info["resolved_url"] = resolved_url
    return info


def download_video(video_url: str, target_path: Path, parts: int = 8) -> dict:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.douyin.com/",
    }

    # 探测是否支持 Range 分块下载，并取总大小
    total = 0
    accept_ranges = False
    try:
        probe = requests.get(video_url, headers={**headers, "Range": "bytes=0-0"}, timeout=15, stream=True)
        if probe.status_code == 206:
            content_range = probe.headers.get("Content-Range", "")  # 形如 bytes 0-0/1234567
            if "/" in content_range:
                total = int(content_range.rsplit("/", 1)[-1])
                accept_ranges = total > 0
        else:
            total = int(probe.headers.get("Content-Length", "0") or "0")
        probe.close()
    except Exception:
        accept_ranges = False

    # 多线程分块并行下载（支持 Range 且 ≥4MB 才值得），失败自动回退单线程
    if accept_ranges and total >= 4 * 1024 * 1024:
        part_size = -(-total // parts)  # 向上取整
        ranges = [(i * part_size, min((i + 1) * part_size - 1, total - 1)) for i in range(parts)]

        def fetch(start: int, end: int) -> tuple:
            r = requests.get(video_url, headers={**headers, "Range": f"bytes={start}-{end}"}, timeout=60)
            r.raise_for_status()
            data = r.content
            r.close()
            return start, data

        try:
            with target_path.open("wb") as f:
                f.truncate(total)
            with concurrent.futures.ThreadPoolExecutor(max_workers=parts) as ex:
                futs = [ex.submit(fetch, s, e) for s, e in ranges]
                with target_path.open("r+b") as f:
                    for fut in concurrent.futures.as_completed(futs):
                        start, data = fut.result()
                        f.seek(start)
                        f.write(data)
            if target_path.stat().st_size == total:
                return {"path": str(target_path), "bytes": total, "content_length": total}
        except Exception:
            pass  # 落到下面的单线程回退

    # 单连接流式下载（回退 / 小文件 / 不支持 Range）
    with requests.get(video_url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", "0") or total or "0")
        written = 0
        with target_path.open("wb") as file:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                file.write(chunk)
                written += len(chunk)
    return {
        "path": str(target_path),
        "bytes": written,
        "content_length": total,
    }


def frame_score(prev_gray, gray) -> float:
    if prev_gray is None:
        return 0.0
    diff = cv2.absdiff(prev_gray, gray)
    return float(diff.mean())


def save_frame(frame, path: Path, max_width: int) -> None:
    height, width = frame.shape[:2]
    if max_width and width > max_width:
        scale = max_width / float(width)
        frame = cv2.resize(frame, (max_width, int(height * scale)), interpolation=cv2.INTER_AREA)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)


def extract_frames(
    video_path: Path,
    frames_dir: Path,
    interval_seconds: float,
    max_frames: int,
    scene_threshold: float,
    min_scene_gap_seconds: float,
    max_width: int,
) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 and frame_count else 0.0

    interval_frames = max(1, int(round(interval_seconds * fps)))
    min_scene_gap_frames = max(1, int(round(min_scene_gap_seconds * fps)))

    frames = []
    prev_small = None
    last_scene_frame = -min_scene_gap_frames
    sample_index = 0
    frame_index = 0
    # 场景检测采样步长：约每 0.1 秒解码一帧比对差异（短剧切镜多在 0.3s 以上，不会漏检），
    # 其余帧用 cap.grab() 仅前进不解码，避免逐帧全解码，大幅提速。
    scene_stride = max(1, int(round(fps * 0.1))) if scene_threshold > 0 else interval_frames

    while True:
        need_sample = frame_index == 0 or frame_index % interval_frames == 0
        need_scene = scene_threshold > 0 and frame_index % scene_stride == 0
        if not (need_sample or need_scene):
            if not cap.grab():          # 仅前进不解码，快速跳过无关帧
                break
            frame_index += 1
            continue

        ok, frame = cap.read()
        if not ok:
            break

        should_sample = need_sample
        score = 0.0
        if need_scene:
            # 在缩小灰度图上算差异，比全分辨率快几十倍
            small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90), interpolation=cv2.INTER_AREA)
            score = frame_score(prev_small, small)
            if (prev_small is not None
                    and score >= scene_threshold
                    and frame_index - last_scene_frame >= min_scene_gap_frames):
                should_sample = True
                last_scene_frame = frame_index
            prev_small = small

        if should_sample:
            timestamp = frame_index / fps if fps else 0.0
            filename = f"frame_{sample_index:04d}_{timestamp:07.2f}s.jpg"
            path = frames_dir / filename
            save_frame(frame, path, max_width)
            frames.append({
                "index": sample_index,
                "frame_number": frame_index,
                "time_seconds": round(timestamp, 3),
                "path": str(path),
                "scene_score": round(score, 3),
            })
            sample_index += 1
            if max_frames > 0 and sample_index >= max_frames:
                break

        frame_index += 1

    cap.release()
    return {
        "fps": round(float(fps), 3),
        "frame_count": frame_count,
        "duration_seconds": round(duration, 3),
        "extracted_count": len(frames),
        "frames": frames,
    }


def build_contact_sheets(frame_data: dict, work_dir: Path, per_sheet: int,
                         max_long: int, scene_threshold: float, quality: int = 88) -> list:
    """把抽好的帧拼成分组 contact sheet（拉片分析用）。缺 PIL 或出错则返回空、不影响主流程。"""
    try:
        from PIL import Image
        from make_contact_sheets import group_frames, choose_grid, build_sheet
    except Exception:
        return []
    items = [
        {"path": Path(fr["path"]), "index": fr["index"], "time": fr["time_seconds"]}
        for fr in frame_data.get("frames", []) or []
    ]
    if not items:
        return []
    scene_set = {
        fr["index"] for fr in frame_data["frames"]
        if float(fr.get("scene_score", 0) or 0) >= scene_threshold
    }
    try:
        with Image.open(items[0]["path"]) as im0:
            ar = im0.size[0] / im0.size[1]
    except Exception:
        return []
    out_dir = work_dir / "contact_sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets = []
    for gi, group in enumerate(group_frames(items, per_sheet, scene_set)):
        cols, rows, tw, th = choose_grid(len(group), ar, max_long)
        fname = f"sheet_{gi:02d}.jpg"
        build_sheet(group, cols, rows, tw, th, scene_set).save(out_dir / fname, quality=quality)
        sheets.append({
            "file": f"contact_sheets/{fname}",
            "grid": [cols, rows],
            "frames": [group[0]["index"], group[-1]["index"]],
            "time_range": [round(group[0]["time"], 2), round(group[-1]["time"], 2)],
            "cells": [
                {"index": it["index"], "time": round(it["time"], 2), "scene_change": it["index"] in scene_set}
                for it in group
            ],
        })
    return sheets


def write_manifest(work_dir: Path, info: dict, video: dict, frame_data: dict,
                   contact_sheets: list = None) -> Path:
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "ready_for_lapian",
        "video_info": info,
        "local_video": video,
        "frame_extraction": frame_data,
    }
    if contact_sheets:
        manifest["contact_sheets"] = contact_sheets
        manifest["agent_next_step"] = [
            "优先读取 contact_sheets[]：每张是一段按时序拼好的分组图，含时间戳/帧号，红框+CUT 标记镜头切换点；据此逐镜分析场景、景别、运镜、人物动作、可见字幕台词、情绪与节奏。",
            "某段细节存疑时，再按 contact_sheets[].cells[].index 到 frame_extraction.frames[] 读取对应原帧放大确认。",
            "不可见或未转写的声音/对白不要编造，只依据画面可见字幕判断。",
        ]
    else:
        manifest["agent_next_step"] = [
            "Read frames in chronological order.",
            "Describe scene, shot size, camera movement, character action, subtitle/dialogue, emotion, and audio cues when visible or inferable.",
            "Do not claim exact dialogue/audio unless it is visible in subtitles or separately transcribed.",
        ]
    path = work_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Douyin share/video URL")
    parser.add_argument("--frame-interval", type=float, default=1.0, help="Sample one frame every N seconds")
    parser.add_argument("--max-frames", type=int, default=120, help="Maximum frames to save; 0 means unlimited")
    parser.add_argument("--scene-threshold", type=float, default=28.0, help="Mean pixel diff threshold for scene-change frames; 0 disables")
    parser.add_argument("--min-scene-gap", type=float, default=0.8, help="Minimum seconds between scene-change frames")
    parser.add_argument("--max-width", type=int, default=960, help="Resize extracted frames to this width")
    parser.add_argument("--sheet-frames", type=int, default=12, help="每张 contact sheet 拼几帧（默认 12）")
    parser.add_argument("--sheet-max-long", type=int, default=1536, help="contact sheet 长边像素上限（默认 1536）")
    parser.add_argument("--no-sheets", action="store_true", help="关闭 contact sheet 生成（兼容旧行为）")
    args = parser.parse_args()

    try:
        info = get_video_info(args.url)
        video_id = info.get("video_id") or safe_name(info.get("title"))
        work_dir = OUTPUT_DIR / safe_name(video_id)
        frames_dir = work_dir / "frames"
        video_path = work_dir / f"{safe_name(video_id)}.mp4"

        if not info.get("video_url"):
            raise RuntimeError("接口未返回 video_url，无法下载视频做画面级拉片")

        video = download_video(info["video_url"], video_path)
        frame_data = extract_frames(
            video_path=video_path,
            frames_dir=frames_dir,
            interval_seconds=args.frame_interval,
            max_frames=args.max_frames,
            scene_threshold=args.scene_threshold,
            min_scene_gap_seconds=args.min_scene_gap,
            max_width=args.max_width,
        )
        sheets = [] if args.no_sheets else build_contact_sheets(
            frame_data, work_dir, args.sheet_frames, args.sheet_max_long, args.scene_threshold
        )
        manifest_path = write_manifest(work_dir, info, video, frame_data, sheets)

        print(json.dumps({
            "status": "ok",
            "video_id": info.get("video_id"),
            "title": info.get("title"),
            "work_dir": str(work_dir),
            "manifest": str(manifest_path),
            "video_path": str(video_path),
            "frames_dir": str(frames_dir),
            "frame_count": frame_data["extracted_count"],
            "duration_seconds": frame_data["duration_seconds"],
            "contact_sheets_dir": str(work_dir / "contact_sheets") if sheets else None,
            "sheet_count": len(sheets),
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
