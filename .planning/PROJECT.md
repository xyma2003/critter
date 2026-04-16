# Critter

## What This Is

Critter 是一个 macOS 桌面宠物应用，常驻桌面右下角作为悬浮 emoji 小猫，点击后展开一个 1024×620 的主面板。主面板包含 AI 对话、热点新闻、宠物互动、便签和设置五个功能区，使用 Python 3.11 + tkinter 构建，支持深色/浅色主题切换。

## Core Value

宠物始终在桌面陪伴——悬浮窗随时可见、可交互，让用户感受到有个小伙伴在场。

## Requirements

### Validated

- ✓ 悬浮猫咪窗口（always-on-top，透明背景，可拖拽）— 初始版本
- ✓ 主面板五 Tab 布局（主页/新闻/宠物/便签/设置）— 初始版本
- ✓ 主页 AI 对话（流式输出，多 session，历史记录）— 初始版本
- ✓ 热点新闻 Tab（百度/微博/Google Trends，自动翻译，定时刷新）— 初始版本
- ✓ 便签 Tab（CRUD，持久化 JSON）— 初始版本
- ✓ 深色/浅色主题切换 — 初始版本
- ✓ 新闻加载动画（双圈旋转 + 🐾 emoji）— v1.1
- ✓ 新闻工具栏按钮加文字说明 — v1.1
- ✓ 应用更名为 Critter — v1.1

### Active

- [ ] 新闻收藏 & 稍后再看（JSON Repository 模式，便于未来迁移数据库）
- [ ] 天气 Tab（wttr.in 免费 API，支持无限城市，可添加/删除）
- [ ] 宠物心情系统（0-100 数值，随时间/互动变化，影响问候语/悬浮 emoji/心情条）
- [ ] 宠物自定义图片（上传本地图片替换 emoji，显示在悬浮窗/对话头像/宠物 Tab）

### Out of Scope

- 云端同步 / 账号系统 — 当前定位本地单机工具，未来里程碑再考虑
- Windows / Linux 支持 — 依赖 macOS 专属 API（透明窗口、通知），暂不跨平台
- 移动端 — 桌面专属场景

## Context

**现有代码库：** `~/.openclaw/workspace/desktop-pet/desktop_pet.py`，约 2056 行，单文件单体架构。

**技术栈：**
- Python 3.11（`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`）
- tkinter 8.6（系统 Python 3.11 自带，macOS 15.x 下系统 Python tkinter 有 bug，必须用此路径）
- 线程模型：daemon thread + `root.after(0, callback)` 回调到主线程
- AI：调用 Claude CLI（`/opt/homebrew/bin/claude --print --output-format stream-json`）
- 数据：JSON 文件（`settings.json`, `notes.json`, `news_cache.json`）

**已知技术债务（来自 CONCERNS.md）：**
- 单文件 2000+ 行，类/函数边界不清晰
- 无 Repository 抽象层，数据读写散落在 UI 代码中
- 拖拽宠物时主面板会被激活（macOS app activation 机制，未完全解决）
- 无测试覆盖

**新功能设计约束：**
- 新闻收藏用 `StorageRepository` 类封装 JSON I/O，为未来数据库迁移预留接口
- 天气使用 wttr.in（`wttr.in/{city}?format=j1`），无需 API key
- 心情值 0-100，持久化到 settings.json，后台定时衰减

## Constraints

- **Tech Stack**: Python 3.11 + tkinter — 不引入第三方 UI 库，保持零依赖安装
- **Python Path**: 必须用 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`，系统 tkinter 有 bug
- **单文件架构**: 当前所有代码在 `desktop_pet.py`，新功能继续在此文件扩展，不拆分模块（避免打破现有启动方式）
- **数据存储**: 当前里程碑用 JSON 文件，但新增数据访问必须通过 Repository 类封装

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 单文件架构继续 | 避免改变启动方式，降低重构风险 | — Pending |
| StorageRepository 模式 | 现在 JSON，未来数据库，上层代码不变 | — Pending |
| wttr.in 天气 API | 免费、无需 key、JSON 格式完善 | — Pending |
| 心情值 0-100 数值制 | 细腻渐变，便于后续扩展更多互动行为 | — Pending |
| 宠物图片支持三处显示 | 悬浮窗 + 对话头像 + 宠物 Tab，体验一致 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-16 after initialization*
