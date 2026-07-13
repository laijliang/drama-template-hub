---
name: libtv-drama
description: >-
  画布编排专用 skill。读取短剧AI全案生成器产出的 JSON，
  在 LibTV 画布上做节点分组、角色三视图占位、720 场景占位、
  分镜表排布和节点连线。只编排不生成，只连线不出图。
---

# LibTV Drama（画布编排）

**这是画布编排 skill，不是内容生成 skill。** 你的输入来自 `短剧AI全案生成器` 产出的 JSON 文件（`Output/{项目名}_全案_{日期}.json`），你只负责在 LibTV 画布上把它变成可视化的编排结构。

> 与 libtv 相关的所有命令以 `libtv --help` / `libtv <子命令> --help` 为准；本 skill 的
> `scripts/` 辅助脚本依赖已安装的 `libtv`（见 libtv-cli skill）。未安装时先装 libtv-cli。

## 输入

用户提供**内容 JSON 的文件路径**（来自 `短剧AI全案生成器` 的产出），你需要读取它：

```bash
CONTENT_JSON="Output/{项目名}_全案_{日期}.json"
```

JSON 中包含你需要的三个数据源：
- `rows[]` — 逐镜数据（`shotNumber`, `imageGenerationPrompt`, `videoMotionPrompt`, `characters[]` 等）
- `characters[]` — 角色资产块（全剧角色列表，含外貌/服装/光影/禁止项）
- `scenes[]` — 场景资产块（全剧场景列表，含色调/光影方案/关键道具）

---

## 工作流

### 0. 准备工作

```bash
cd d:/Manage_Drama
CONTENT_JSON="Output/{项目名}_全案_{日期}.json"
# 确认文件存在
if [ ! -f "$CONTENT_JSON" ]; then echo "❌ 未找到内容 JSON，请先运行短剧AI全案生成器"; exit 1; fi
```

### 1. 登录检查

```bash
"$LIBTV_BIN" account info 2>&1 || "$LIBTV_BIN" login web
```

未登录则提示用户在浏览器完成授权。

### 2. 建工作区 + 画布

```bash
bash "skill/libtv-drama/scripts/build_canvas.sh" "$CONTENT_JSON" "{项目名}"
# 输出：CANVAS_LINK=https://www.liblib.tv/canvas?spaceId=<WS>&projectId=<PRJ>
```

> ⚠️ 拿到 `CANVAS_LINK` 后**立刻返回给用户**，后续编排可继续。

### 3. 读取 JSON — 提取结构化数据

用 bash + `jq`（或 `python3 -c`）从 JSON 中提取编排所需信息：

```bash
# 角色列表
jq '.characters[] | {name: .characterName, id: .characterId, costume: .costume, lighting: .lighting}' "$CONTENT_JSON"

# 场景列表
jq '.scenes[] | {name: .sceneName, id: .sceneId, type: .type, lighting: .lightingPlan}' "$CONTENT_JSON"

# 分镜总数
jq '.rows | length' "$CONTENT_JSON"

# 每镜涉及的场景（sceneTags）和角色（characters[].characterName）
jq '.rows[] | {shot: .shotNumber, scene: .sceneTags, chars: [.characters[].characterName]}' "$CONTENT_JSON"
```

### 4. 创建角色分组节点（三视图占位）

每个角色创建一个 "角色-{名字}" text 节点，内容填写其资产信息，作为后续三视图出图的提示词源：

```bash
for row in $(jq -c '.characters[]' "$CONTENT_JSON"); do
  name=$(echo "$row" | jq -r '.characterName')
  desc=$(echo "$row" | jq -r '.characterDescription')
  costume=$(echo "$row" | jq -r '.costume.default')
  lighting=$(echo "$row" | jq -r '.lighting')

  "$LIBTV_BIN" node create "角色-${name}" -t text \
    --content "Character: ${name}
Description: ${desc}
Default Costume: ${costume}
Lighting: ${lighting}
---
三视图提示词（供后续生图用）：
Front view: Full body front view of ${desc}, wearing ${costume}, ${lighting}
Side view: Profile view of ${desc}, wearing ${costume}
Back view: Back view of ${desc}, wearing ${costume}"
done
```

### 5. 创建场景节点（720 场景占位）

每个场景创建一个 "场景-{sceneName}" text 节点，作为后续 720 场景图的提示词源：

```bash
for row in $(jq -c '.scenes[]' "$CONTENT_JSON"); do
  name=$(echo "$row" | jq -r '.sceneName')
  desc=$(echo "$row" | jq -r '.description')
  lighting=$(echo "$row" | jq -r '.lightingPlan')
  tone=$(echo "$row" | jq -r '.colorTone')
  props=$(echo "$row" | jq -r '.props | join(", ")')

  "$LIBTV_BIN" node create "场景-${name}" -t text \
    --content "Scene: ${name}
Description: ${desc}
Lighting Plan: ${lighting}
Color Tone: ${tone}
Key Props: ${props}
---
720 scene reference prompt（供后续生图用）:
360 degree panoramic view of ${desc}, ${lighting}, ${tone}, 8K photorealistic"
done
```

### 6. 创建分镜表节点

```bash
"$LIBTV_BIN" node create "分镜表" -t storyboard \
  -u rows=$(jq '.rows' "$CONTENT_JSON")
```

### 7. 节点连线

> **画布连线规则**：storyboard 上游必须是 text 节点，不能连另一个 script 节点。

将分镜表与各角色/场景节点建立关联：

```bash
# 分镜表 ← 所有角色节点
for row in $(jq -c '.characters[]' "$CONTENT_JSON"); do
  name=$(echo "$row" | jq -r '.characterName')
  "$LIBTV_BIN" node "分镜表" --left "角色-${name}"
done

# 分镜表 ← 所有场景节点
for row in $(jq -c '.scenes[]' "$CONTENT_JSON"); do
  name=$(echo "$row" | jq -r '.sceneName')
  "$LIBTV_BIN" node "分镜表" --left "场景-${name}"
done
```

### 8. 交付

返回给用户：
1. **画布链接** `CANVAS_LINK`
2. 已完成的分组结构：角色节点数、场景节点数、分镜表镜数
3. 说明：角色三视图和 720 场景图**未自动生成**，用户可在画布上手动触发或后续通过其他 skill 批量生成

---

## 踩坑清单

1. **ID 解析**：`workspace create` 返回 `"workspaceId": 2301858`（冒号后**有空格**），
   `project create` 返回 `"uuid":"6137282c2d5645bc9fd39e2ca74172c2"`（**32 位无连字符**，不是 36 位 UUID）。
   正则要用 `"workspaceId": *[0-9]+` 和 `"uuid": *"[0-9a-f]{32}"`。
2. **节点子命令**：建节点是 `libtv node create <name> ...`，修改是 `libtv node <name> -u ...`；
   漏掉 `create` 会报语法错。
3. **storyboard 上游**：`--left` 上游必须是 `text` 或参考图，**不能**是另一个 `script` 节点。
4. **不要自动生图/生视频**：本 skill 只做编排连线，不调用任何 generate/run 命令。
5. **JSON 解析**：用 `jq` 解析 JSON，没有则用 `python3 -c "import sys,json;..."` 替代。
6. **节点查询延迟**：`libtv node <name>` 即时返回可能是旧状态；以创建时返回的 ID 为准。

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 本编排工作流文档 |
| `scripts/build_canvas.sh` | 建工作区+画布，读 JSON 中的项目信息初始化画布 |
