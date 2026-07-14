# coding=utf-8
"""
抖音视频信息提取脚本
被 短剧AI全案生成器 skill 调用的接口脚本。
用法: python get_douyin_video.py <视频链接>
输出: 结构化 JSON（到 stdout），供 agent 做拉片分析

依赖: 本仓库内的 DouYin_Spider/（第三方项目 cv-cat/Douyin_Spider）。
      可用环境变量 DOUYIN_SPIDER_PATH 指向别处；需要在 DouYin_Spider/.env 配置抖音 cookie。
"""
import json
import os
import sys
import re
import builtins
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# DouYin_Spider 爬虫项目：默认用本仓库内的 DouYin_Spider/，
# 也可用环境变量 DOUYIN_SPIDER_PATH 指向别处
SPIDER_PATH = Path(os.environ.get(
    "DOUYIN_SPIDER_PATH",
    str(Path(__file__).resolve().parent.parent / "DouYin_Spider"),
))
sys.path.insert(0, str(SPIDER_PATH))

try:
    if not hasattr(builtins, "long"):
        builtins.long = int
    if not hasattr(builtins, "basestring"):
        builtins.basestring = str
    if not hasattr(builtins, "unicode"):
        builtins.unicode = str
    import requests
    from dotenv import load_dotenv
    from utils.common_util import load_env
    from dy_apis.douyin_api import DouyinAPI
except ModuleNotFoundError as e:
    missing = e.name or str(e)
    print(json.dumps({
        "error": "missing_dependency",
        "message": f"缺少 Python 依赖: {missing}",
        "install": f"python -m pip install -r {SPIDER_PATH / 'requirements.txt'}",
    }, ensure_ascii=False, indent=2))
    sys.exit(2)


def normalize_douyin_url(url: str) -> str:
    """Resolve Douyin share links and return a canonical work URL."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    if "v.douyin.com" in url:
        resp = requests.get(
            url,
            allow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        url = resp.url

    video_match = re.search(r"(?:douyin|iesdouyin)\.com/(?:share/)?video/(\d+)", url)
    if video_match:
        return f"https://www.douyin.com/video/{video_match.group(1)}"

    modal_match = re.search(r"modal_id=(\d+)", url)
    if modal_match:
        return f"https://www.douyin.com/video/{modal_match.group(1)}"

    raise ValueError(f"无法从链接中解析抖音作品 ID: {url}")


def extract_video_info(auth, url: str) -> dict:
    """获取视频信息，输出结构化数据"""
    result = DouyinAPI.get_work_info(auth, url)
    data = result.get("aweme_detail")

    if not data:
        return {
            "error": "获取失败",
            "raw": result.get("filter_detail", {}).get("filter_reason", "未知"),
        }

    # 提取话题标签
    topics = []
    for t in data.get("text_extra", []) or []:
        if t.get("hashtag_name"):
            topics.append(t["hashtag_name"])

    # 提取视频地址（请勿外传！用于拉片分析）
    video_url = ""
    if data.get("video") and data["video"].get("play_addr"):
        urls = data["video"]["play_addr"]["url_list"]
        if urls:
            video_url = urls[0]

    return {
        "video_id": data["aweme_id"],
        "title": data.get("desc", ""),
        "author": {
            "nickname": data["author"]["nickname"],
            "uid": data["author"].get("sec_uid", ""),
            "signature": data["author"].get("signature", ""),
            "follower_count": data["author"].get("follower_count", 0),
        },
        "stats": {
            "digg_count": data["statistics"]["digg_count"],
            "comment_count": data["statistics"]["comment_count"],
            "collect_count": data["statistics"]["collect_count"],
            "share_count": data["statistics"]["share_count"],
            "play_count": data["statistics"].get("play_count", 0),
        },
        "topics": topics,
        "cover_url": data["video"]["cover"]["url_list"][0] if data.get("video") else "",
        "video_url": video_url,
        "create_time": data["create_time"],
    }


def check_environment():
    """运行前自检 DouYin_Spider 环境，缺什么就给出可照做的中文指引。"""
    problems = []
    env_file = SPIDER_PATH / ".env"
    if not env_file.exists():
        problems.append(
            f"未配置抖音 cookie：请把 {SPIDER_PATH / '.env.example'} 复制为 {env_file}，"
            "再填入登录抖音后从浏览器复制的 DY_COOKIES"
        )
    else:
        load_dotenv(env_file)
        if not os.environ.get("DY_COOKIES"):
            problems.append(
                f"{env_file} 里的 DY_COOKIES 为空：请填入登录抖音后从浏览器复制的整段 cookie"
            )
    if not (SPIDER_PATH / "node_modules").exists():
        problems.append(
            f'缺少 node 依赖（抖音签名需要）：请执行  cd "{SPIDER_PATH}" && npm install'
        )
    return problems


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供视频链接"}, ensure_ascii=False))
        sys.exit(1)

    try:
        problems = check_environment()
        if problems:
            print(json.dumps({
                "error": "environment_not_ready",
                "message": "DouYin_Spider 环境未就绪，请先完成以下配置后重试：",
                "steps": problems,
            }, ensure_ascii=False, indent=2))
            sys.exit(3)
        url = normalize_douyin_url(sys.argv[1])
        auth = load_env()
        info = extract_video_info(auth, url)
        info["resolved_url"] = url
        print(json.dumps(info, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
