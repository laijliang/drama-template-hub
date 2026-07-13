#!/usr/bin/env bash
# build_canvas.sh — 读内容 JSON，建工作区+画布+全部分组节点+连线，打印画布链接
# 依赖：已安装的 libtv + jq（无 jq 则用 python3 兜底）
# Usage: build_canvas.sh <content_json_path> [theme]
#   例: build_canvas.sh "Output/井底之蛙_全案_20260712.json"
set -uo pipefail

LIBTV="${LIBTV_BIN:-C:/Users/34355/.libtv/libtv.exe}"
CONTENT_JSON="$1"
THEME="${2:-}"
PROJDIR="${PROJDIR:-.}"
cd "$PROJDIR" || { echo "[build_canvas] ERROR: cannot cd $PROJDIR" >&2; exit 1; }
err(){ echo "[build_canvas] ERROR: $1" >&2; exit 1; }

[ -f "$CONTENT_JSON" ] || err "content json not found: $CONTENT_JSON"
[ -x "$LIBTV" ] || echo "[build_canvas] WARN: libtv not executable at $LIBTV, relying on PATH" >&2

# ---- 从 JSON 提取信息 ----
# 用 jq，没有则用 python3 兜底
if command -v jq &>/dev/null; then
  JQ() { jq -r "$1" "$CONTENT_JSON"; }
  JQ_A() { jq -c "$1" "$CONTENT_JSON"; }
else
  JQ() { python3 -c "import sys,json; d=json.load(open('$CONTENT_JSON')); print($1)"; }
  JQ_A() { python3 -c "import sys,json; d=json.load(open('$CONTENT_JSON')); [print(json.dumps(x,ensure_ascii=False)) for x in $1]"; }
fi

if [ -z "$THEME" ]; then
  THEME=$(JQ 'd.get("track","") or d.get("viral_reason","") or "Untitled"')
fi
echo "[build_canvas] Theme: $THEME"

# ---- 登录检查 ----
ACCT=$("$LIBTV" account info 2>&1)
if ! echo "$ACCT" | grep -q '"activeAccount"'; then
  echo "[build_canvas] 未登录，启动 web 登录..."
  "$LIBTV" login web
  ACCT=$("$LIBTV" account info 2>&1)
  echo "$ACCT" | grep -q '"activeAccount"' || err "登录后仍未拿到有效账号"
fi
echo "$ACCT" | grep -oE '"effective":[ ]*(true|false)' | head -1 | sed 's/^/[build_canvas] 账号等级 /'

# ---- 1) 工作区 ----
WSOUT=$("$LIBTV" workspace create "$THEME" -d "${THEME} 漫剧" 2>&1) || err "workspace create failed"
WS=$(echo "$WSOUT" | grep -oE '"workspaceId": *[0-9]+' | grep -oE '[0-9]+' | head -1)
[ -n "$WS" ] || err "cannot parse workspaceId from: $WSOUT"
"$LIBTV" workspace use "$WS" >/dev/null 2>&1
echo "[build_canvas] Workspace: $WS"

# ---- 2) 画布 ----
PRJOUT=$("$LIBTV" project create "${THEME}-画布" -d "$THEME" 2>&1) || err "project create failed"
PRJ=$(echo "$PRJOUT" | grep -oE '"uuid": *"[0-9a-f]{32}"' | grep -oE '[0-9a-f]{32}' | head -1)
[ -n "$PRJ" ] || err "cannot parse project uuid from: $PRJOUT"
"$LIBTV" project use "$PRJ" >/dev/null 2>&1
echo "[build_canvas] Project: $PRJ"

# ---- 3) 主题概念节点 ----
"$LIBTV" node create "主题概念" -t text \
  --prompt "主题《${THEME}》" >/dev/null 2>&1

# ---- 4) 角色分组节点（三视图占位） ----
while IFS= read -r row; do
  [ -z "$row" ] && continue
  name=$(echo "$row" | python3 -c "import sys,json; print(json.load(sys.stdin).get('characterName',''))" 2>/dev/null)
  [ -z "$name" ] && continue
  echo "[build_canvas]   Creating character node: 角色-${name}"
  "$LIBTV" node create "角色-${name}" -t text \
    --content "$(echo "$row" | python3 -c "
import sys,json
d=json.load(sys.stdin)
lines=[
    f'Character: {d.get(\"characterName\",\"\")}',
    f'Description: {d.get(\"characterDescription\",\"\")}',
    f'Default Costume: {d.get(\"costume\",{}).get(\"default\",\"\")}',
    f'Lighting: {d.get(\"lighting\",\"\")}',
    '---',
    'Front view: Full body front view of ' + d.get('characterDescription',''),
    'Side view: Profile view of ' + d.get('characterDescription',''),
    'Back view: Back view of ' + d.get('characterDescription',''),
]
print('\\n'.join(lines))
")" >/dev/null 2>&1
  "$LIBTV" node "角色-${name}" --left 主题概念 >/dev/null 2>&1
done < <(python3 -c "
import sys,json
d=json.load(open('$CONTENT_JSON'))
chars = d.get('characters',[]) or []
for c in chars: print(json.dumps(c,ensure_ascii=False))
" 2>/dev/null)

# ---- 5) 场景节点（720 场景占位） ----
while IFS= read -r row; do
  [ -z "$row" ] && continue
  name=$(echo "$row" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sceneName',''))" 2>/dev/null)
  [ -z "$name" ] && continue
  echo "[build_canvas]   Creating scene node: 场景-${name}"
  "$LIBTV" node create "场景-${name}" -t text \
    --content "$(echo "$row" | python3 -c "
import sys,json
d=json.load(sys.stdin)
lines=[
    f'Scene: {d.get(\"sceneName\",\"\")}',
    f'Description: {d.get(\"description\",\"\")}',
    f'Lighting Plan: {d.get(\"lightingPlan\",\"\")}',
    f'Color Tone: {d.get(\"colorTone\",\"\")}',
    f'Key Props: {\", \".join(d.get(\"props\",[]) or [])}',
    '---',
    '360 degree panoramic view of ' + d.get('description',''),
]
print('\\n'.join(lines))
")" >/dev/null 2>&1
  "$LIBTV" node "场景-${name}" --left 主题概念 >/dev/null 2>&1
done < <(python3 -c "
import sys,json
d=json.load(open('$CONTENT_JSON'))
scenes = d.get('scenes',[]) or []
for s in scenes: print(json.dumps(s,ensure_ascii=False))
" 2>/dev/null)

# ---- 6) 分镜表节点 ----
ROWS=$(python3 -c "
import sys,json
d=json.load(open('$CONTENT_JSON'))
print(json.dumps(d.get('rows',[]) or [], ensure_ascii=False, separators=(',',':'))
)
")
if [ -n "$ROWS" ] && [ "$ROWS" != "[]" ]; then
  echo "[build_canvas]   Creating storyboard node with ${#ROWS} shots"
  "$LIBTV" node create "分镜表" -t storyboard >/dev/null 2>&1
  "$LIBTV" node "分镜表" -u "rows=${ROWS}" >/dev/null 2>&1 || err "push rows to 分镜表 failed"
  "$LIBTV" node "分镜表" --left 主题概念 >/dev/null 2>&1
  # 分镜表连所有角色和场景
  while IFS= read -r row; do
    name=$(echo "$row" | python3 -c "import sys,json; print(json.load(sys.stdin).get('characterName',''))" 2>/dev/null)
    [ -n "$name" ] && "$LIBTV" node "分镜表" --left "角色-${name}" >/dev/null 2>&1
  done < <(python3 -c "
import sys,json
d=json.load(open('$CONTENT_JSON'))
for c in (d.get('characters',[]) or []): print(json.dumps(c,ensure_ascii=False))
")
  while IFS= read -r row; do
    name=$(echo "$row" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sceneName',''))" 2>/dev/null)
    [ -n "$name" ] && "$LIBTV" node "分镜表" --left "场景-${name}" >/dev/null 2>&1
  done < <(python3 -c "
import sys,json
d=json.load(open('$CONTENT_JSON'))
for s in (d.get('scenes',[]) or []): print(json.dumps(s,ensure_ascii=False))
")
else
  echo "[build_canvas]   WARN: no rows found in JSON, skipping storyboard node"
fi

# ---- 打印画布链接 ----
echo "CANVAS_LINK=https://www.liblib.tv/canvas?spaceId=${WS}&projectId=${PRJ}"
echo "WS=${WS}"
echo "PRJ=${PRJ}"
echo "[build_canvas] 画布已就绪：角色节点 $(python3 -c "import json; d=json.load(open('$CONTENT_JSON')); print(len(d.get('characters',[]) or []))") 个，场景节点 $(python3 -c "import json; d=json.load(open('$CONTENT_JSON')); print(len(d.get('scenes',[]) or []))") 个，分镜 $(python3 -c "import json; d=json.load(open('$CONTENT_JSON')); print(len(d.get('rows',[]) or []))") 镜"
