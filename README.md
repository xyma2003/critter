# Critter

macOS 桌面宠物应用。一只边牧常驻桌面，右键选择“打开面板”进入主面板，包含 AI 对话、热点新闻、宠物互动、便签、天气、日记、设置 7 个 Tab。

**Tech stack**: Python 3.11 + PyQt6 (UI) + LangGraph (agent orchestration) + langchain-anthropic (LLM) + requests/BeautifulSoup (news scraping)

## 功能（7 Tab）

- **聊天（AI 对话）**：气泡聊天。关键词触发 LangGraph agent（理解→规划→执行→反思→回复），普通对话按配置使用 OpenAI-compatible API 或 Claude CLI。已有会话会保存，但会话选择入口与连续上下文仍待完善
- **热点新闻**：抓取百度热搜 / 今日头条热榜，英文标题自动翻译，书签/稍后再看
- **宠物互动**：心情 / 饱食 / 精力三维状态，喂食、逗宠、休息
- **便签**：轻量便签，标题 + 内容
- **天气**：wttr.in 天气查询，多城市管理
- **日记**：基于当天互动记录，Claude CLI 自动生成宠物视角日记
- **设置**：宠物名/性格/口头禅、深色/浅色主题

## 前提条件

- **macOS**（`utils/objc.py` 使用 ctypes 调用 libobjc 管理窗口层级）
- **Python 3.10+**
- **LLM API Key**（二选一）：
  - SiliconFlow（国内推荐，[获取地址](https://cloud.siliconflow.cn/)）
  - Anthropic（[申请地址](https://console.anthropic.com/)）
- **[Claude CLI](https://claude.ai/code) 在 PATH 中**（仅 Anthropic 模式需要，日记生成 fallback 会调用；SiliconFlow 模式不需要）
  - 安装：`npm install -g @anthropic-ai/claude-code`（需 Node.js 18+）

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/xyma2003/critter.git
cd critter
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API credentials

```bash
cp .env.example .env
# Edit .env — fill in ONE backend (see .env.example comments)
```

**Option A — SiliconFlow / OpenAI-compatible（国内推荐）**：
- `.env` 文件配置 `OPENAI_API_KEY` + `OPENAI_API_BASE` + `OPENAI_MODEL`
- 适用于国内环境，无需 VPN
- 获取 key：https://cloud.siliconflow.cn/

**Option B — Anthropic（海外）**：
- `ANTHROPIC_API_KEY` 环境变量（或 `.env` 文件）
- Claude CLI 需在 PATH 中（见前提条件）

`.env` 示例（SiliconFlow）：
```bash
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen3-32B
```

> 当 `OPENAI_API_KEY` 设了，agent 和日记生成都走 SiliconFlow；否则 fallback 到 Anthropic + Claude CLI。

### 5. Run

```bash
.venv/bin/python main.py
```

也可以在 Finder 中双击 `启动桌面宠物.command`。脚本会自动进入它所在的项目目录，并使用该目录下的 `.venv/bin/python`；项目可以放在包含空格或中文的路径中，双击前无需手动激活虚拟环境。宠物窗口会显示在桌面上；右键点击宠物并选择“打开面板”，即可进入主面板。

首次使用需完成上面的依赖安装；使用 AI 功能时再按上文配置凭据。启动脚本会检查 Python 版本和依赖是否存在；环境不完整或程序异常退出时，终端会显示错误和下一步操作，按回车即可关闭。它不会自动安装依赖或更改配置。

如果提示缺少虚拟环境或依赖，在项目目录运行：

```bash
python3 -m venv .venv          # 使用 Python 3.10+；已有 .venv 时跳过此行
.venv/bin/python -m pip install -r requirements.txt
```

## 资源与本地数据

项目目录与用户数据分开定位，不受启动时的工作目录影响：

| 内容 | 位置 |
| --- | --- |
| 配置文件 | 当前项目目录下的 `.env`，不会搜索其他目录的同名文件 |
| 宠物资源 | 当前项目目录下的 `assets/animations/<pet>/<state>.gif`；目前未附带 GIF，缺失时继续显示 emoji |
| 默认用户数据 | `~/.desktop-pet-state.json`，与旧版本保持一致 |
| 自定义用户数据 | 设置 `CRITTER_DATA_DIR` 后，使用该目录下的 `state.json` |

聊天、便签和日记、宠物状态、设置等仍由同一个状态文件保存。设置页会显示本次运行实际使用的文件路径，可选中复制。移动或重新克隆项目不会改变默认数据位置，现有数据不需要迁移。

需要隔离运行时，可在 `.env` 中配置 `CRITTER_DATA_DIR`，也可以在启动时传入：

```bash
CRITTER_DATA_DIR="$HOME/Library/Application Support/Critter" .venv/bin/python main.py
```

目录必须是绝对路径，也支持 `~/...`；相对路径会被明确拒绝，防止切换工作目录后误用另一份数据。父目录在首次保存时创建。启动时显式设置的 `CRITTER_DATA_DIR` 优先于 `.env`，未设置或空值沿用旧版默认位置。

自定义目录不会自动导入或覆盖默认文件。若想把旧数据转过去：先退出所有 Critter 实例并备份原文件，确认目标目录没有需要保留的 `state.json`，再把备份复制过去并命名为 `state.json`。修改配置、重启后，在设置页核对路径与原有便签、设置；原文件继续保留。取消 `CRITTER_DATA_DIR` 即恢复使用默认位置。

旧配置中的 OpenClaw 固定目录和未使用的头像、日志路径常量已移除；本次不会读取或搬动该目录中的文件。

### 保存失败与损坏文件

保存时先将完整内容写到同目录临时文件，同步后再替换状态文件。写入失败时，上次成功保存的文件仍保留；这次修改留在当前进程内存，界面顶部显示“尚未保存”及具体类别。处理目录权限或磁盘空间问题后，点击“重试保存”，会一并保存所有待保存修改；后续一次成功的保存也会带上这些修改。

待保存修改不保证在强制结束进程或断电后恢复。通过应用正常退出时，会先尝试保存；仍失败则可重试、取消退出或明确选择“不保存并退出”。不要同时运行多个实例编辑同一个状态文件：当前只串行处理同一进程内的写入，未提供跨进程合并。

若状态文件不是有效的 JSON 对象，Critter 会先在原目录保留一份 `原文件名.corrupt-时间-随机标识.bak`，并持续显示备份提示。首次启动没有可用快照时从空状态继续；若运行中才发现损坏，会保留本次会话中最后读到的数据及待保存修改。备份保存的是原始字节，不代表已修复或恢复其中的数据；查看信息并确认只会关闭提示，不会删除备份。需要手动恢复时，先退出应用，保留当前文件和备份，再修复副本中的 JSON。启动时若现有文件无法读取，或损坏原件无法备份，应用会停止启动并提示重试，避免按空数据覆盖原件。

存储故障检查使用临时文件和故障注入，包含 Qt 离屏启动、退出及界面流程，不访问真实用户数据：

```bash
.venv/bin/python -m unittest tests.test_state_manager tests.test_application tests.test_storage_notice -v
```

### 便签标识与旧数据兼容

新便签和日记使用独立的 UUID 标识，更新时间仍保留时间戳。同一秒创建多条记录也可以分别编辑、删除。原本唯一的旧整数 ID 保持不变；首次读取发现重复 ID 时，仅为重复组内各条记录重新分配标识，内容、顺序、日期及其他字段不变。旧的歧义 ID 不再指向其中任何一条，界面会使用修复后的标识。

标识修复沿用上述安全保存机制：写入失败时保留在当前会话，并显示未保存提醒；重试成功后，重启仍使用同一组标识。

```bash
.venv/bin/python -m unittest tests.test_notes tests.test_notes_panel -v
```

### 路径与旧数据兼容检查

```bash
.venv/bin/python -m unittest tests.test_paths -v
```

检查使用临时项目与合成旧数据，覆盖更换目录、中文及空格路径、配置优先级、重启读写和旧数据保留，不读取真实用户状态或调用模型。

### 启动脚本回归检查

```bash
python3 tests/test_launcher.py
```

这组检查使用临时目录和模拟解释器，验证路径、环境选择及失败提示，不会启动桌宠、访问网络或调用模型。

### 主面板检查（无需模型）

```bash
.venv/bin/python -m unittest tests.test_panel -v
```

使用临时状态和 Qt 离屏窗口，检查七个页面、最小窗口尺寸、浅深色聊天气泡、长消息与配置说明。不会操作桌面或发起模型请求。主页与设置中的 AI 状态仅表示检测到本机配置，不代表连接或登录已经验证；宠物互动与便签可离线使用。

## 项目结构

```
Critter/
├── main.py                    # 入口
├── 启动桌面宠物.command          # macOS 双击启动脚本
├── config.py                  # Config 类 + 环境配置
├── paths.py                   # 项目资源定位 + 兼容旧状态文件的路径解析
├── core/                      # PyQt6 核心
│   ├── pet_window.py          # PetWindow 悬浮宠物窗口
│   ├── main_panel.py          # MainPanel 主面板（7 Tab）
│   ├── animation_manager.py   # 动画状态机
│   ├── event_handler.py       # 鼠标拖拽/点击
│   ├── state_manager.py       # JSON 持久化层
│   └── greeting.py            # 时间/久别重逢问候
├── agent/                     # LangGraph Agent
│   ├── graph.py               # 工作流：understand→plan→execute→reflect→respond
│   ├── nodes.py               # 各节点 LLM 调用
│   ├── tools.py               # get_news / set_timer 工具
│   └── state.py               # AgentState TypedDict
├── features/                  # 功能插件
│   ├── base_feature.py        # ABC 基类
│   ├── news_push/             # 新闻推送
│   └── timer/                 # 倒计时闹钟
├── services/                  # 业务服务
│   ├── weather/               # wttr.in 天气 + 缓存
│   ├── diary/                 # Claude CLI 日记生成
│   ├── notes/                 # 便签 CRUD
│   └── chat_history/          # 聊天 session 持久化
├── data/pet/__init__.py       # PetStats 状态管理
├── ui/                        # PyQt6 复用组件
│   ├── theme.py               # 全局 QSS 主题
│   ├── chat_list.py           # 气泡聊天列表
│   ├── feature_button.py      # 功能按钮
│   └── speech_bubble.py       # 宠物头顶气泡
├── utils/                     # 工具
│   ├── network.py             # HTTP 封装
│   ├── objc.py                # macOS Objective-C 桥
│   ├── screen_utils.py        # 屏幕尺寸
│   └── translator.py          # 翻译占位
└── tests/                     # pytest 天气服务单测
```

## 依赖

依赖包括：PyQt6, langgraph, langchain-anthropic, langchain-openai, langchain-core, anthropic, requests, beautifulsoup4, lxml, Pillow, python-dotenv。详见 `requirements.txt`。
