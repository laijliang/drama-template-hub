# coding=utf-8
"""
Prepare Douyin video assets for shot-by-shot analysis.

Usage:
  python scripts/prepare_douyin_lapian.py "<douyin url>"

Output:
  A local mp4, extracted frames, and a manifest JSON under Output/media/<video_id>/.
"""
import argparse
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


def download_video(video_url: str, target_path: Path) -> dict:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.douyin.com/",
    }
    with requests.get(video_url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", "0") or "0")
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
    prev_gray = None
    last_scene_frame = -min_scene_gap_frames
    sample_index = 0
    frame_index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        should_sample = frame_index == 0 or frame_index % interval_frames == 0
        gray = None
        score = 0.0

        if scene_threshold > 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = frame_score(prev_gray, gray)
            scene_changed = (
                prev_gray is not None
                and score >= scene_threshold
                and frame_index - last_scene_frame >= min_scene_gap_frames
            )
            if scene_changed:
                should_sample = True
                last_scene_frame = frame_index
            prev_gray = gray

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


def write_manifest(work_dir: Path, info: dict, video: dict, frame_data: dict) -> Path:
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "ready_for_lapian",
        "video_info": info,
        "local_video": video,
        "frame_extraction": frame_data,
        "agent_next_step": [
            "Read frames in chronological order.",
            "Describe scene, shot size, camera movement, character action, subtitle/dialogue, emotion, and audio cues when visible or inferable.",
            "Do not claim exact dialogue/audio unless it is visible in subtitles or separately transcribed.",
        ],
    }
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
        manifest_path = write_manifest(work_dir, info, video, frame_data)

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
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
