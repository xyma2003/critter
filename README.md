# Critter

macOS 桌面宠物应用。一只边牧常驻桌面右下角，点击后展开主面板，包含 AI 对话、热点新闻、宠物互动、便签、天气、日记、设置 7 个 Tab。

**Tech stack**: Python 3.11 + PyQt6 (UI) + LangGraph (agent orchestration) + langchain-anthropic (LLM) + requests/BeautifulSoup (news scraping)

## 功能（7 Tab）

- **主页（AI 对话）**：流式气泡聊天，支持多 Session 历史、用户画像记录。关键词触发 LangGraph agent（理解→规划→执行→反思→回复），否则走 Claude CLI
- **热点新闻**：抓取百度热搜 / 今日头条热榜，英文标题自动翻译，书签/稍后再看
- **宠物互动**：心情 / 饱食 / 精力三维状态，喂食、逗宠、休息
- **便签**：轻量便签，标题 + 内容
- **天气**：wttr.in 天气查询，多城市管理
- **日记**：基于当天互动记录，Claude CLI 自动生成宠物视角日记
- **设置**：宠物名/性格/口头禅、深色/浅色主题

## 启动

```bash
pip install -r requirements.txt
python3 main.py
```

需要：
- `ANTHROPIC_API_KEY` 环境变量（或 `.env` 文件），用于 LangGraph Agent
- [Claude CLI](https://claude.ai/code) 在 PATH 中（AI 对话和日记生成会调用）
- macOS（`utils/objc.py` 使用 ctypes 调用 libobjc 管理窗口层级）

## 项目结构

```
Critter/
├── main.py                    # 入口
├── config.py                  # Config 类 + 路径常量
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

依赖包括：PyQt6, langgraph, langchain-anthropic, langchain-core, anthropic, requests, beautifulsoup4, lxml, Pillow, python-dotenv。
