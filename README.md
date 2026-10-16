# Critter

一只住在 macOS 桌面的边牧。陪你聊几句，接住随手记下的灵感，也把今天的互动写成日记。

**macOS · Python / PyQt6 · 本地保存 · AI 按需配置**

[开始使用](#开始使用) · [AI 配置](docs/configuration.md) · [使用与数据](docs/usage-and-storage.md) · [演示与复现](docs/demo.md)

![Critter 聊天界面：奶油色主面板、已保存会话和连续对话](docs/images/chat.png)

*本文界面图片为真实 Qt 界面渲染，使用合成对话和固定离线回复。它们展示应用流程，不代表真实模型回复效果；[演示说明与复现](docs/demo.md)。*

## 桌边多一个小伙伴

<img src="assets/animations/border_collie/idle_sleep.gif" width="150" alt="Critter 自带的边牧打盹动画">

它会打盹、摇尾，也会回应你的点击。打开宠物面板，可以喂食、玩耍、抚摸或让它休息；每次互动都会留下记录。基础角色动画已经随仓库提供，安装后就能用。

![宠物面板：心情、饱食度、精力和四种互动操作](docs/images/pet.png)

桌面角色、宠物互动、便签和主题设置都不需要模型凭据。右键桌宠，选择“打开面板”，就能开始。

## 聊天可以接着说

配置 AI 后，Critter 会结合当前会话继续回答。你可以给它取名字、调整性格和口头禅，也可以在已保存会话间切换，重启后再接着聊。每次请求使用最近 **20 条消息、12,000 个 Unicode 字符**以内的上下文；保存在本地的完整历史与模型上下文是两回事。

等待回复时，发送按钮会暂停，你仍可编辑下一条草稿。完成或失败后可以继续发送；切换会话时，旧回复不会混入新对话。失败提示不进入模型上下文，CLI 聊天有 120 秒回复等待上限。

[会话恢复、删除、上下文限制与检查](docs/usage-and-storage.md#连续聊天与人设)

## 把今天的小事写进日记

日记页会先列出当天记录的喂食、玩耍、抚摸与休息次数，再用点击生成时的快照请求 AI 写一段宠物视角的日记。生成结果保存到便签，之后可以回看和编辑。

![宠物日记：当天互动计数、本次生成依据和日记正文](docs/images/diary.png)

没有记录时会显示零次，并要求模型不编造互动；当前心情只是生成时的快照。生成需要 AI 配置，旧版本没有保存的活动无法补回。[互动记录与日记依据](docs/usage-and-storage.md#互动记录与日记依据)

## 开始使用

需要 **macOS、Python 3.10+**。先启动本地功能，再决定是否配置 AI：

```bash
git clone https://github.com/xyma2003/critter.git
cd critter
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

首次启动不需要 `.env` 或 API Key。桌宠出现后，右键选择“打开面板”。完成依赖安装后，也可以在 Finder 双击 `启动桌面宠物.command`；脚本会使用当前项目的 `.venv`，支持中文和空格路径，无需先激活环境。

启动脚本会检查 Python 版本与依赖；环境不完整或程序异常退出时，终端会保留错误和下一步操作。它不会自动安装依赖或修改配置。若提示缺少虚拟环境或依赖，重新执行上面的建环境与安装步骤；已有 `.venv` 时跳过创建。

## 还有这些日常功能

| 内容 | 使用条件 |
| --- | --- |
| 桌面动画、宠物互动、便签、人设与主题设置 | 本地使用，无需模型凭据 |
| 回看已保存的聊天与日记 | 本地使用；产生新的 AI 回复需要配置 |
| 百度热搜、今日头条热榜与原文链接 | 需要网络；不需要模型 Key |
| 添加城市、查询天气 | 使用 wttr.in，需要网络；不需要模型 Key |
| AI 聊天、生成日记 | OpenAI-compatible API 或已配置的 Claude CLI |
| Agent 获取新闻、设置倒计时 | 需要 API 配置；CLI 登录不能替代 Agent API 凭据 |

当前提供一套基础边牧角色。新闻翻译函数仍为占位，当前没有自动翻译、书签或稍后再看功能。新闻与天气依赖外部服务，可能受上游变化影响。

## 接入 AI

普通聊天、Agent 与日记使用的路径有所不同：

| 配置 | 普通聊天与日记生成 | 关键词触发的 Agent |
| --- | --- | --- |
| `OPENAI_API_KEY`、`OPENAI_API_BASE`、`OPENAI_MODEL` | 使用所配兼容 API | 使用同一 API；模型需支持工具调用 |
| Claude CLI + `ANTHROPIC_API_KEY` | 使用 CLI | 使用 Anthropic API |
| 只有 Claude CLI | 可使用 CLI | 仍需另外配置 API |
| 只有 `ANTHROPIC_API_KEY` | 仍需 CLI 或兼容 API | 使用 Anthropic API |

`OPENAI_API_KEY` 非空时优先选择兼容 API；请求失败不会自动切换供应商。首页与设置页显示的是检测到的本机配置，不代表连接或 CLI 登录已经验证。

复制 `.env.example` 前先看[配置说明](docs/configuration.md)。示例默认不启用任何模型，按需要填写；服务可用性、支持的模型和费用以所用供应商为准。

## 你的数据放在哪里

默认保存在 `~/.desktop-pet-state.json`，也可以通过 `CRITTER_DATA_DIR` 指定独立目录。设置页可以查看实际路径；保存失败会提示尚未保存，并提供重试。不要同时启动多个实例修改同一份数据。

[数据位置、迁移、损坏备份与恢复](docs/usage-and-storage.md#资源与本地数据)

## 维护状态与参与

- **当前状态：** 面向 macOS 的本地桌宠项目，已提供基础动画、会话管理、聊天忙碌与失败处理、互动记录、便签和日记流程。离线回归检查验证请求与界面流程，真实模型回复质量仍需单独评估。
- **已知限制：** 其他桌面平台未验证；模型上下文受前述条数与字符上限约束；新闻、天气依赖外部服务。目前[天气回包](core/main_panel.py)没有绑定城市请求身份，快速切换城市时可能把旧数据显示在当前城市名下。
- **下一小步（尚未实现）：** 为天气请求加入城市和请求标识，隔离迟到结果；这是天气流程的改进，与已完成的聊天忙碌锁分开。
- **一个具体贡献任务：** 参考[天气服务的模拟方式](tests/test_weather_service.py)和[Qt 离屏界面夹具](tests/test_panel.py)，增加“A 城市先请求、B 城市后请求，B 先完成、A 后完成”的用例，并修复请求归属。验收时最终只显示 B 的城市名与数据，A 的迟到成功或错误都不覆盖 B，未结束的线程保持有效引用。用临时状态和模拟服务完成，不请求真实天气或模型。

发现问题可[提交 Issue](https://github.com/xyma2003/critter/issues/new)，附仓库提交、macOS/Python 版本、相关配置模式、最小复现步骤、期望与实际表现，以及已去除密钥和个人信息的日志。不要附 `.env`、真实聊天记录或状态文件。PR 保持一个明确问题，说明实际运行的检查和仍未覆盖的范围。

## 开发与检查

项目使用 PyQt6 构建界面、LangGraph 编排 Agent；应用依赖见 [requirements.txt](requirements.txt)。离线检查使用临时状态与模拟服务，不会调用真实模型。

```bash
.venv/bin/python -m pip install -r requirements.txt 'pytest>=8,<10'
QT_QPA_PLATFORM=offscreen PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests -q
```

测试依赖 `pytest` 需另外安装。检查通过表示所覆盖的流程符合预期，不代表真实模型输出、服务连接或 CLI 认证已经验证。[分项检查与项目结构](docs/usage-and-storage.md)

代码与仓库自带角色按 [MIT License](LICENSE) 分发。角色由项目内代码绘制，详见[素材来源、许可与生成脚本](assets/animations/border_collie/README.md)。
