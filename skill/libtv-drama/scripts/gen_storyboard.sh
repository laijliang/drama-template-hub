#!/usr/bin/env bash
# gen_storyboard.sh — 从 shots.txt 逐镜串行生成分镜图（Seedream 4.6）
# 依赖：已安装的 libtv。二进制路径可用 LIBTV_BIN 覆盖。
# 输入 shots.txt 格式：每行  shotNumber<TAB>imageGenerationPrompt
# Usage: gen_storyboard.sh <shots.txt> [project_uuid] [sleep_seconds] [ratio]
#   例: gen_storyboard.sh shots.txt 6137282c... 14 9:16
# 输出：每行  shotN<TAB>imageURL  （同时写入 gen_urls.txt 供下载）
set -uo pipefail

LIBTV="${LIBTV_BIN:-C:/Users/34355/.libtv/libtv.exe}"
SHOTS="$1"; PRJ="${2:-}"; SLEEP="${3:-14}"; RATIO="${4:-9:16}"
PROJDIR="${PROJDIR:-.}"
cd "$PROJDIR" || { echo "[gen_storyboard] ERROR: cannot cd $PROJDIR" >&2; exit 1; }
err(){ echo "[gen_storyboard] ERROR: $1" >&2; exit 1; }

[ -f "$SHOTS" ] || err "shots.txt not found: $SHOTS"
[ -n "$PRJ" ] && "$LIBTV" project use "$PRJ" >/dev/null 2>&1
: > gen_urls.txt

while IFS=$'\t' read -r shot prompt; do
  [ -z "${shot:-}" ] && continue
  echo "[gen_storyboard] shot $shot generating..." >&2
  LOG="/tmp/gen_shot_${shot}.log"
  "$LIBTV" node create "分镜图-$shot" -t image \
    -s "model=Seedream 4.6" -s "ratio=$RATIO" -s count=1 \
    --prompt "$prompt" --run > "$LOG" 2>&1
  rc=$?
  url=$(grep -oE 'https://libtv-res[^"]+\.png' "$LOG" 2>/dev/null | head -1)
  if [ -n "$url" ]; then
    echo "shot${shot}	${url}"
    echo "shot${shot}	${url}" >> gen_urls.txt
  else
    echo "[gen_storyboard] WARN shot $shot: no url (rc=$rc). log tail:" >&2
    tail -5 "$LOG" >&2
    echo "shot${shot}	FAILED"
    echo "shot${shot}	FAILED" >> gen_urls.txt
  fi
  # 免费账号并行上限=1，必须串行 + 释放槽位
  sleep "$SLEEP"
done < "$SHOTS"

echo "[gen_storyboard] DONE. 结果见 gen_urls.txt" >&2
