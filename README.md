# Manage_Drama — AI 漫剧（短剧）创作工作流

> 从一个故事构思或一条爆款视频链接出发，完成**拉片分析 → 结构化全案生成 → 前端模板库展示**的完整流水线。

---

## 一、项目概述

本项目是一个 AI 漫剧（短剧）创作工具链，核心能力是：

1. **拉片分析**：输入抖音爆款视频链接，自动下载视频、抽帧、提取元数据，做逐镜画面分析
2. **全案生成**：将故事构思或拉片分析结果，编译为结构化 JSON 全案包（含角色/场景/道具资产块 + 逐镜中文分镜）
3. **前端展示**：通过 `site/index.html` 仪表盘浏览、筛选、管理所有全案模板，并一键复制分镜与资产

**设计原则**：只生产结构化 JSON 内容，不生成图片/视频；分镜与素材统一为中文，供人直接阅读与复制。

---

## 快速开始（环境配置）

> **前端 + "文字剧情 → 生成全案" 开箱即用；只有"从抖音链接拉片"才需要额外配 DouYin_Spider + cookie。**

### 最省事：让 Claude Code 帮你一键装配

如果你用 **Claude Code**（VS Code 插件或 CLI，**不是网页版**），在一个空文件夹里把下面这句话发给它，它会帮你 clone、装依赖、写 cookie、跑通验证，全程不用自己敲命令：

> 帮我克隆 `https://github.com/laijliang/drama-template-hub`，按 README 的「快速开始」装好 Python 与 DouYin_Spider 的依赖；我的抖音 cookie 是 `<粘贴你的 cookie>`，帮我写进 `DouYin_Spider/.env`，然后跑一下 `scripts/get_douyin_video.py` 验证。

**前提**：机器上要先有 `git` / `Python 3` / `Node.js`（这三个运行时 Claude 装不了，需自备）；网络能访问 GitHub 与 npm（国内一般要开代理）。抖音 cookie 是登录凭据、会过期，过期后重配一次即可。

> 只想用前端浏览、或只用「文字剧情 → 生成全案」的话，连 cookie 和 DouYin_Spider 都不用——见下面 A。

### A. 只用前端 / 文字剧情生成（零配置）
- **前端**：直接双击打开 `site/index.html`，或部署到 GitHub Pages 浏览
- **生成全案**：用 Claude Code 打开本仓库，按 `skill/短剧AI全案生成器.md`，给一段剧情或文字描述即可生成全案 JSON —— 这条链不碰抖音、无需任何依赖

### B. 需要"从抖音链接拉片"时（可选）

> 下面命令里的 `python` / `pip`：Windows 直接用；**macOS/Linux 若没有这两个命令，改用 `python3` / `pip3`**。

1. **装 Python 依赖**
   ```bash
   pip install -r requirements.txt
   ```
   > 只需装**根目录**这一份 `requirements.txt`（已覆盖拉片脚本 + DouYin_Spider 实际用到的依赖）。`DouYin_Spider/requirements.txt` 是上游第三方项目的原始清单，含本项目用不到的包（loguru/retry/openpyxl 等），**不必单独安装**。
2. **装 Node.js**（DouYin_Spider 的签名 JS 靠它执行），并安装其 npm 依赖
   ```bash
   cd DouYin_Spider && npm install && cd ..
   ```
   > ⚠️ 依赖里的 `canvas` 是**原生模块**，`npm install` 需要本机有编译环境，装不上多半是缺下面这些：
   > - **Windows**：装 [Visual Studio Build Tools]（勾选「C++ 生成工具」）
   > - **macOS**：`brew install pkg-config cairo pango libpng jpeg giflib librsvg`
   > - **Linux**：`sudo apt install build-essential libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev`
3. **配置抖音 cookie**：把 `DouYin_Spider/.env.example` 复制成 `DouYin_Spider/.env`，填入你登录抖音后的 cookie（`.env` 已被 gitignore，不会上传）
   ```bash
   cp DouYin_Spider/.env.example DouYin_Spider/.env   # 然后编辑，填入 DY_COOKIES
   ```
4. **跑通验证**
   ```bash
   python scripts/get_douyin_video.py "<抖音视频链接>"
   python scripts/prepare_douyin_lapian.py "<抖音视频链接>"   # 下载+抽帧+拼图
   ```
   > 环境没配齐时脚本会直接告诉你缺哪一步（cookie 没填 / 没 `npm install`），照提示补上即可，不会再报看不懂的错误码。

> `DouYin_Spider/` 是第三方开源项目 [cv-cat/Douyin_Spider](https://github.com/cv-cat/Douyin_Spider) 的代码（已随本仓库提供；cookie 与 node_modules 需自行配置/安装）。要指向别处的 DouYin_Spider，设环境变量 `DOUYIN_SPIDER_PATH` 即可。

#### 拉片装不上 / 跑不通？常见报错速查

> 拉片是本项目门槛最高的一环（要 Node 原生编译 + 抖音 cookie + 通常还要代理）。对号入座：

| 现象 / 报错 | 原因 | 解决 |
|------|------|------|
| `npm install` 卡在 `canvas` 编译失败（`node-gyp` / `gyp ERR`） | `canvas` 是原生模块，缺 C++ 编译环境 | 按上面「⚠️ canvas 原生模块」装好对应平台的构建工具（Windows: VS Build Tools 勾 C++；mac: `brew install pkg-config cairo pango libpng jpeg giflib librsvg`；Linux: 装 `libcairo2-dev` 等），再重跑 `npm install` |
| `npm install` / `git clone` 一直超时 | 国内网络访问 npm / GitHub 受限 | 开代理，或给 npm 设国内镜像：`npm config set registry https://registry.npmmirror.com` |
| 脚本提示「未配置抖音 cookie / DY_COOKIES 为空」 | 没建 `.env` 或没填 cookie | 复制 `.env.example` 为 `.env`，填入登录抖音后从浏览器 F12 → Network 里复制的整段 Cookie |
| 之前能跑，现在返回登录/风控/空数据 | 抖音 cookie 已过期 | 重新登录抖音，复制新 cookie 覆盖 `.env` 里的 `DY_COOKIES` |
| 脚本提示「缺少 node 依赖」 | 没执行 `npm install` | `cd DouYin_Spider && npm install && cd ..` |
| `ModuleNotFoundError: cv2 / requests / ...` | 没装 Python 依赖 | 在项目根执行 `pip install -r requirements.txt`（Win 用 `pip`，mac/Linux 用 `pip3`） |
| `protobuf` 相关的运行时版本错误 | protobuf 版本与 `_pb2.py`（5.27.1 生成）不兼容 | `requirements.txt` 已把 `protobuf` 锁在 `>=5.27,<8`；若手动升过版，按此区间重装 |

> 只是想用前端浏览、或「文字剧情 → 全案」的话，以上全都不需要——见上面 **A. 零配置**。

---

## 二、目录结构

```
Manage_Drama/
├── site/                         # 前端仪表盘站点
│   ├── index.html                #   仪表盘（拉片·短剧全案库）
│   ├── data/
│   │   └── templates.json        #   前端模板数据库（同步到 GitHub Pages）
│   └── dist/                     #   部署产物（由 index.html+data 生成，可重建）
├── scripts/                      # 抖音数据采集脚本
│   ├── get_douyin_video.py       #   获取视频元数据（标题/作者/互动/视频地址）
│   ├── prepare_douyin_lapian.py  #   下载视频 + 抽帧 + 分组拼图 + manifest
│   └── make_contact_sheets.py    #   独立拼图工具（对已抽好的 frames/ 生成拼图）
├── skill/                        # AI Agent 技能定义
│   └── 短剧AI全案生成器.md        #   内容生成 skill（三阶段产出 JSON）
├── Output/                       # 产出目录
│   ├── *_全案_*.json             #   完整全案 JSON
│   └── media/{video_id}/         #   下载的视频与抽帧图片
│       ├── {video_id}.mp4
│       ├── frames/frame_*.jpg           #   逐帧图（原样保留，供定向放大）
│       ├── contact_sheets/sheet_*.jpg   #   分组拼图（拉片分析优先读这个）
│       └── manifest.json
├── README.md
└── .gitignore
```

---

## 三、完整工作流

### 总览

```
用户输入（故事构思 / 抖音链接 / 视频描述）
         │
         ▼
  ┌──────────────────────────┐
  │  阶段 A：数据采集（可选） │  ← 仅当输入是视频链接时
  │  scripts/get_douyin_video.py     获取元数据
  │  scripts/prepare_douyin_lapian.py 下载+抽帧
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │  阶段 B：全案生成         │  ← skill: 短剧AI全案生成器
  │  阶段一：项目资产锚定     │     角色/场景/道具/美术规则
  │  阶段二：逐镜分镜脚本     │     中文 shots[]
  │  阶段三：输出打包 JSON    │     → Output/{项目名}_全案_{日期}.json
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │  阶段 C：前端展示         │  ← site/index.html
  │  site/data/templates.json │     仪表盘浏览 / 管理 / 复制
  └──────────────────────────┘
```

---

### 阶段 A：数据采集（抖音视频链接 → 元数据 + 抽帧）

当用户提供抖音爆款视频链接时，先采集原始数据供分析。

#### A1. 获取视频元数据

```bash
# 在项目根目录执行；Windows 用 python，macOS/Linux 用 python3
python scripts/get_douyin_video.py "<抖音视频链接>"
```

**脚本功能**：
- 解析分享链接（`v.douyin.com` 短链 → 标准视频 URL）
- 调用仓库内的 `DouYin_Spider` 项目获取视频详情
- 输出结构化 JSON 到 stdout：

| 字段 | 说明 |
|------|------|
| `video_id` | 抖音作品 ID |
| `title` | 视频描述/标题 |
| `author` | 作者昵称、签名、粉丝数 |
| `stats` | 点赞/评论/收藏/分享数 |
| `topics` | 话题标签列表 |
| `cover_url` | 视频封面图 URL |
| `video_url` | 视频下载地址（用于拉片） |
| `create_time` | 发布时间戳 |

#### A2. 下载视频 + 抽帧（画面级拉片）

```bash
# 在项目根目录执行；Windows 用 python，macOS/Linux 用 python3
python scripts/prepare_douyin_lapian.py "<抖音视频链接>" --frame-interval 0.5 --max-frames 0
```
> 默认 `--frame-interval 0.5`（2 帧/秒，避免漏字幕）、`--max-frames 0`（不限帧数，长视频不截断）。

**脚本功能**：
- 调用 A1 获取视频地址
- 下载 MP4 到 `Output/media/{video_id}/{video_id}.mp4`
- 使用 OpenCV 按时间间隔抽帧 + 场景切换检测（`scene_threshold=28.0`）
  - 采用**跳帧解码**（`cap.grab()` 跳过无关帧）+ **降采样场景检测**（约每 0.1 秒在缩小灰度图上比对差异），抽帧解码比逐帧快约 3–4 倍，抽帧结果基本一致
- 帧图保存到 `Output/media/{video_id}/frames/frame_XXXX_XXX.XXs.jpg`
- **分组拼图（contact sheet）**：把抽好的帧按场景切换均分成若干张网格拼图（默认每张 12 帧，长边 ≤1536px），每格标时间戳/帧号、镜头切换帧标红框 + CUT，存到 `Output/media/{video_id}/contact_sheets/sheet_*.jpg`
  - 目的：拉片分析时**分批读拼图（每批 3–5 张，可并行、时序上下文完整）**、按时序读完全部，而非逐张读几十上百帧；某段存疑再定向读原帧，大幅减少读图次数
  - 参数：`--sheet-frames`（每张帧数）、`--sheet-max-long`（长边上限）、`--no-sheets`（关闭，完全兼容旧行为）
- 生成 `manifest.json`（拉片素材清单），包含：
  - `video_info`：视频元数据
  - `local_video`：本地视频路径与大小
  - `frame_extraction`：FPS、总帧数、时长、抽帧列表（每帧含时间戳、路径、场景变化分数）
  - `contact_sheets`：每张拼图的 `file` / `grid` / `frames` / `time_range` / `cells`（含每格时间戳、是否切换帧）

> **依赖**：`opencv-python-headless`、`requests`、`python-dotenv`、`Pillow`，以及仓库内的 `DouYin_Spider`。
>
> 独立工具 `scripts/make_contact_sheets.py` 可对已抽好的 `frames/` 直接生成拼图（不必重新下载视频），用法：`python scripts/make_contact_sheets.py <frames_dir> [--per-sheet 12] [--max-long 1536]`。

---

### 阶段 B：全案生成（skill: 短剧AI全案生成器）

这是内容生成的核心阶段，产出一份机器和人都能读的结构化 JSON。

#### 输入场景

| 场景 | 输入 | 处理方式 |
|------|------|----------|
| A | 用户给了剧情/故事构思 | 直接进入分析流程 |
| B | 用户给了爆款视频链接 | 先执行阶段 A 数据采集，再分析 |
| C | 用户直接提供了视频文字描述 | 基于描述直接分析 |

#### 复刻规则（核心原则）

当用户要求"复刻"一个视频时，严格遵守 **"内核不变，故事换新"**：

**保留不变的结构 DNA**：赛道、核心情绪、3 秒钩子类型、情绪曲线、叙事结构、冲突类型、视听基调

**必须完全换新**：场景、具体冲突、道具/关键物件、台词/对白、视觉元素

> 宁可"看起来是完全不同的故事，但感觉一样"——也不要"看起来一样，只是换了个名字"。

#### 三阶段输出

##### 阶段一：项目资产锚定

建立全案的"宪法"，后续所有阶段强制绑定：

- **项目基础信息**：名称、类型、画风、色调、目标受众、镜头节奏
- **全局美术规则**：时代背景、画面风格、禁止元素、剧情约束
- **主角人设资产包**：姓名、五官、发型、常服、性格、专属光影、禁止崩坏项
- **配角人设资产包**：每个配角同结构
- **场景资产库**：室内/室外/专属场景 + 固定光影方案
- **全局 AI 生成强制锁规则**：五官/画风/质量全程锁定

##### 阶段二：逐镜分镜脚本

将剧情编译为逐镜分镜（中文），每一镜包含：
- `name`：镜号-场景名
- `tag`：情绪/阶段标签
- `durationSeconds`：预计时长（秒）
- `description`：整合描述（画面内容 + 镜头语言 + 构图 + 光影 + 表情 + 动作 + 台词；**不正向写音效/BGM**）
- `negativePrompt`：逐镜负向/逆向提示词——**音频只保留对白**、不要 BGM/环境音/音效/旁白配音；画面不要烧录字幕/水印/logo；不要畸形手指/多指/崩坏/穿帮（POV 镜追加：不露"我"正脸）

> 不生成英文 `rows` 或英文生图/生视频提示词。分镜统一为中文 `shots`。生成的是**只带对白的干净片段**，BGM/音效/字幕一律后期另加。

##### 阶段三：输出打包 JSON

文件路径：`Output/{项目名}_全案_{日期}.json`

JSON 结构：

```
{
  // ── 前端展示字段 ──
  "video_source": "",           // 视频来源
  "tracks": [],                 // 基础赛道（固定 11 类：情感/搞笑/悬疑/治愈/逆袭/知识/萌宠/古风/玄幻/都市/剧情类，可多选，不得自造）
  "core_emotion": "",           // 核心情绪
  "hook_type": "",              // 钩子类型
  "perspective": "",            // 叙事视角：第一人称POV / 第三人称（拉片必判，复刻须保留）
  "viral_reason": "",           // 爆款原因

  "script": {                   // 剧本结构
    "structure": "",
    "acts": [{ "title": "", "tag": "", "content": "" }]
  },

  "analysis": [...],            // 分析（角色/冲突/情绪曲线/节奏等）
  "shots": [...],               // 逐镜分镜（中文，含 name/tag/durationSeconds/description/negativePrompt）
  "prompts": {                  // 中文提示词包
    "镜头提示词(中文生图用)": "",
    "画面提示词(生视频用)": "",
    "风格提示词(统一画风用)": "",
    "负向提示词(通用逆向-整片复用)": ""   // 一条整片通用的负向提示词，可一键复制套用
  },
  "connection": "",             // 使用说明
  "external_models": [...],     // 推荐外部模型

  // ── 独立资产块（素材库）──
  "characters": [{              // 角色资产
    "characterName": "", "characterId": "",
    "gender": "", "age": 0,
    "appearance": { "face": "", "hair": "", "body": "", "distinctive": "" },
    "costume": { "default": "", "colorPalette": [], "prohibited": "" },
    "lighting": "", "emotions": []
  }],

  "scenes": [{                  // 场景资产
    "sceneName": "", "sceneId": "",
    "type": "", "description": "",
    "lightingPlan": "", "colorTone": "",
    "props": [], "prohibited": ""
  }],

  "props": [{                   // 道具资产（关键叙事道具）
    "propName": "", "propId": "",
    "type": "", "description": "",
    "symbolism": "",            // 象征意义
    "lockedDetails": "",        // 跨镜锁定细节
    "appearsIn": "",            // 出现镜次
    "prohibited": ""
  }]
}
```

---

### 阶段 C：前端展示（index.html）

一个白蓝主题的仪表盘，浏览和管理所有全案模板。

#### 功能模块

| 模块 | 功能 |
|------|------|
| **首页** | 精选 Hero 卡片（镜数最多的全案）、最近导入列表、右栏赛道快捷筛选、累计分镜环形图与快速统计 |
| **模板库** | 全案卡片网格，支持按赛道/情绪筛选 + 关键词搜索 |
| **素材库** | 汇总所有全案的角色/场景/道具，按类型展示，每张卡可复制 |
| **数据统计** | 模板数、分镜总数、累计时长、角色/场景数、赛道分布柱状图、情绪分布 |
| **设置** | 本地存储信息、GitHub Pages 同步状态、清空数据 |

#### 数据流

```
data/templates.json  ←(GitHub Pages 部署后同步)→  index.html
         ↓
  localStorage（离线缓存）
         ↓
  渲染：卡片 / 素材 / 统计 / 详情抽屉
```

- **本地打开**（`file://` 协议）：直接读 localStorage，首次加载内嵌数据
- **在线访问**（GitHub Pages 等）：`fetch('data/templates.json')` 同步最新数据
- **导入**：粘贴 JSON 或选择文件，去重后写入 localStorage
- **导出**：下载全部模板为 JSON 文件

#### 详情抽屉（点击卡片打开）

展示单套全案的完整信息：
- 基础信息（赛道、情绪、钩子、爆款原因）
- 剧本结构（三幕/多幕）
- 分析报告（角色/冲突/情绪曲线/节奏）
- **素材库**：角色/场景/道具资产卡片，每张卡可**一键复制**（复制中文全字段，并自动追加对应的生成提示词）
- **分镜脚本**：逐镜中文分镜列表，支持单镜复制 / 全部复制
- 提示词包（中文生图/生视频/风格提示词）

#### 资产复制的自动提示词

复制角色/场景/道具卡片时，文本 = 该资产的全部中文字段 + 末尾自动追加一句生成提示词（提示词本身不在页面显示）：

| 资产 | 追加的提示词 |
|------|------|
| 角色 | 帮我生成这个角色的正面站立全身图，要写实风格，背景纯色。比例9：16。 |
| 场景 | 帮我生成这个场景的场景图，要写实电影风格。比例16：9。 |
| 道具 | 帮我生成这个物品的三视图（输出图片左中右等比例分出来三个区域，一个区域分别显示一个视图），背景纯色，要写实电影风格。比例16：9。 |

---

## 四、数据流转全景

```
                    ┌─────────────────────────────────┐
                    │         用户输入                 │
                    │  故事构思 / 抖音链接 / 视频描述   │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │    scripts/get_douyin_video.py   │
                    │    → 视频元数据 JSON (stdout)    │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │  scripts/prepare_douyin_lapian.py│
                    │  → Output/media/{id}/            │
                    │    ├ {id}.mp4                    │
                    │    ├ frames/frame_*.jpg          │
                    │    └ manifest.json               │
                    └────────────┬────────────────────┘
                                 │
              ┌──────────────────▼──────────────────────┐
              │     skill: 短剧AI全案生成器              │
              │     ├ 阶段一：资产锚定                   │
              │     ├ 阶段二：逐镜分镜                   │
              │     └ 阶段三：JSON 打包                  │
              │     → Output/{项目名}_全案_{日期}.json   │
              └──────────────────┬──────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │       前端 index.html            │
                    │       ↓                          │
                    │       data/templates.json        │
                    │       ↓                          │
                    │       localStorage 缓存          │
                    │       ↓                          │
                    │       仪表盘渲染                 │
                    │       ├ 模板库                   │
                    │       ├ 素材库（可复制）         │
                    │       ├ 数据统计                 │
                    │       └ 详情抽屉（分镜/资产复制） │
                    └──────────────────────────────────┘
```

---

## 五、已有产出物

### Output/ 目录

| 文件 | 类型 | 说明 |
|------|------|------|
| `Output/*_全案_*.json`（当前 6 套） | 完整全案 | 新格式，含 `shots[]`（每镜带 `negativePrompt`）+ `characters[]` + `scenes[]` + `props[]` |
| `media/{video_id}/` | 拉片素材 | 抖音视频下载 + 抽帧 + manifest.json |

已有全案：妈妈的栀子花 / 巷口那碗面 / 九十九只鱼干 / 妈妈家里还有我 / 逆火而行 / 这场暴雪是难忘一课。

### data/templates.json

当前汇总 6 套模板，供前端仪表盘展示（与 `Output/` 全案保持同步）。

### 部署（GitHub Pages）

项目已部署为静态站点，入口在 `site/index.html`，由 `.github/workflows/pages.yml`（GitHub Actions）在 push 到 `main` 时把 `site/` 目录发布到 Pages。

| 项 | 值 |
|------|------|
| 线上地址 | https://laijliang.github.io/drama-template-hub/ |
| 仓库 | https://github.com/laijliang/drama-template-hub |
| 线上数据源 | `data/templates.json`（在线访问时由前端 `fetch` 加载） |
| 更新方式 | 改动 push 到 `main`，GitHub Pages 自动重新构建（约 1–2 分钟生效） |
| 不上传项（`.gitignore`） | `Output/media/`（版权视频/抽帧）、`__pycache__/`、`.claude/settings.local.json`、`.workbuddy/` |

> 每次改完 `site/index.html` 或新增全案后，记得把最新全案汇总进 `site/data/templates.json` 再 push，线上才会同步展示。

---

## 六、使用指南

### 场景 1：从故事构思生成全案

1. 告诉 AI 你的故事构思
2. AI 调用 `短剧AI全案生成器` skill，三阶段产出 JSON
3. JSON 保存到 `Output/{项目名}_全案_{日期}.json`
4. 将 JSON 导入前端仪表盘

### 场景 2：从抖音链接复刻爆款

1. 提供抖音视频链接
2. AI 自动采集视频元数据 + 下载抽帧
3. 基于拉片分析提取结构 DNA，按复刻规则生成全新故事
4. 产出全案 JSON → 导入前端

### 场景 3：前端模板库管理与创作

1. 本地打开 `site/index.html`（或访问线上地址）
2. 点击「导入」粘贴全案 JSON 或选择文件
3. 浏览模板库、素材库、数据统计
4. 点击卡片查看详情，复制分镜（中文）或复制角色/场景/道具资产（自动带生成提示词），拿去 AI 绘图工具生成图片

---

## 七、技术栈与依赖

| 组件 | 技术/依赖 |
|------|-----------|
| 数据采集 | Python 3、`requests`、`python-dotenv`、`DouYin_Spider`（随仓库提供） |
| 视频抽帧 | `opencv-python-headless`（跳帧解码 + 场景检测） |
| 分组拼图 | `Pillow`（拼网格 + 标注时间戳/切换帧，供拉片分析） |
| 内容生成 | AI Agent skill（`短剧AI全案生成器.md`） |
| 前端 | 原生 HTML/CSS/JS（无框架）、localStorage、GitHub Pages 同步 |

---

## 八、关键设计决策

1. **只生产内容**：`短剧AI全案生成器` 只产出结构化 JSON，不生成图片/视频。图片交由用户复制资产提示词后在外部 AI 绘图工具生成。

2. **中文优先**：分镜统一为中文 `shots[]`（`name` / `tag` / `durationSeconds` / `description`），资产字段也全为中文，不再生成英文 `rows` 或英文提示词字段，让 skill 响应更快、产出更贴合中文创作者。

3. **复刻不等于换皮**：严格保留原作的结构 DNA（赛道/情绪/叙事/冲突），但场景/角色/台词/道具全部换新。输出前逐条自查。

4. **资产块独立**：`characters[]` / `scenes[]` / `props[]` 作为独立资产块，不再混入分镜描述中重复。道具升级为含象征意义和跨镜锁定细节的独立资产。前端"素材库"直接读这三个资产块，不再单列 `materials`。

5. **前端兼容双格式**：`site/index.html` 同时兼容早期 `rows[]` 格式和新版 `shots[]` 格式，`buildShotList()` 自动适配（旧版从结构化字段拼成中文分镜）。

6. **复制即创作**：分镜和每个资产都可一键复制；资产复制会自动追加对应的中文生成提示词（全身图 9:16 / 场景图 16:9 / 三视图 16:9），复制出来即可直接喂给 AI 绘图工具。
