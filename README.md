# Critter

macOS 桌面宠物应用。一只 emoji 小猫常驻桌面右下角，点击后展开包含 AI 对话、热点新闻、宠物互动、便签和设置的主面板。

**Tech stack**: Python 3.11 + tkinter（零第三方依赖）

## 功能

- **AI 对话**：流式气泡聊天，支持多 Session 历史、用户画像记录
- **热点新闻**：抓取 Google Trends / 百度 / 微博，英文标题自动翻译，书签/稍后再看
- **宠物互动**：心情 / 饱食 / 精力三维状态，喂食、逗猫、休息
- **便签**：轻量 Markdown 便签
- **设置**：宠物 emoji、尺寸、新闻刷新间隔、深色/浅色主题

## 启动

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 main.py
```

> 必须使用 Python.org 3.11，系统自带 tkinter 8.5 在 macOS 15.x 上有渲染 bug。

## 项目结构

```
Critter/
├── main.py              # 入口
├── config.py            # 主题色、路径常量
├── data/
│   ├── repository.py    # 书签持久化（StorageRepository）
│   ├── pet_stats.py     # 心情/饱食/精力状态
│   └── settings.py      # JSON 读写工具
├── services/
│   ├── news.py          # 新闻抓取、缓存、翻译
│   └── ai.py            # Claude CLI 调用封装
├── ui/
│   ├── panel.py         # MainPanel（主面板，5 个 Tab）
│   └── pet_window.py    # DesktopPet（悬浮宠物窗口）
├── settings.json        # 用户配置
├── notes.json           # 便签数据
└── bookmarks.json       # 书签数据
```

## 依赖

- Python 3.11+（标准库，无需 pip install）
- [Claude CLI](https://claude.ai/code) 安装在 `/opt/homebrew/bin/claude`（AI 对话 & 新闻翻译）
- macOS（使用 ctypes 调用 Objective-C runtime 管理窗口层级）
