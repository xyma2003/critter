# AI 与运行配置

[返回首页](../README.md) · [使用、保存与检查](usage-and-storage.md) · [演示说明](demo.md)

桌面角色、宠物互动、便签、主题与人设设置无需模型凭据。新闻和天气需要网络，但不使用模型 API。只有新的 AI 回复、日记生成和 Agent 请求需要下面的配置。

## 先选需要的能力

| 配置 | 普通聊天 | 日记生成 | 关键词触发的 Agent |
| --- | --- | --- | --- |
| OpenAI-compatible API 的 Key、Base URL 和模型 ID | 兼容 API | 兼容 API | 同一兼容 API；需要工具调用支持 |
| 已配置的 Claude CLI + Anthropic API Key | Claude CLI | Claude CLI | Anthropic API |
| 只有已配置的 Claude CLI | Claude CLI | Claude CLI | 仍需 API 凭据 |
| 只有 Anthropic API Key | 仍需 CLI 或兼容 API | 仍需 CLI 或兼容 API | Anthropic API |

普通聊天与日记在 `OPENAI_API_KEY` 非空时使用兼容 API，否则尝试 Claude CLI。Agent 在同一变量非空时也使用兼容 API，否则使用 Anthropic API。**这是按配置选择路径，不是请求失败后自动切换后端。**

## 配置文件

在项目目录复制模板；已有 `.env` 时直接编辑，不要用模板覆盖现有配置：

```bash
cp .env.example .env
```

模板中的模型字段默认注释，不会把示例 Key 当作真实配置。不使用 AI 时，不需要创建 `.env`。

程序只读取当前项目目录下的 `.env`，不会查找其他工作目录的同名文件。该文件中的模型配置会覆盖同名进程环境变量；`CRITTER_DATA_DIR` 是例外，启动时显式传入的值优先。配置修改后请重启 Critter。不要将填入真实凭据的 `.env` 提交到仓库。

## OpenAI-compatible API

取消以下三项的注释，填入所用服务给出的 Key、兼容 API 地址和模型 ID：

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://your-provider.example/v1
OPENAI_MODEL=your-model-id
```

上面是格式说明，不能直接作为有效配置使用。这里的 `OPENAI_*` 是应用读取的变量名，不限定服务供应商。普通聊天和日记需要兼容 Chat Completions；Agent 还需要所选服务与模型支持工具调用。

若没有显式设置 Base URL 或模型，当前代码使用 `https://api.siliconflow.cn/v1` 和 `Qwen/Qwen3-32B` 作为默认值。建议完整填写三项，避免把一个供应商的 Key 发给另一个地址。这些代码默认值不表示已验证当前服务、模型或价格，使用前应核对自己的服务配置。

`OPENAI_API_KEY` 只要非空就会选择这条路径，不会先验证是否有效。切换到 CLI / Anthropic 路径时，需移除它或设为空，同时检查进程环境中是否还有同名变量。不要填入占位 Key 或空格来表示“尚未配置”。

## Claude CLI 与 Anthropic API

这两项承担不同的工作，可以按需要分别配置：

- **Claude CLI**：用于普通聊天和日记。`claude` 需要在本机可执行，并已完成该 CLI 所要求的认证与配置。应用从 `PATH` 查找，找不到时还会尝试 `/opt/homebrew/bin/claude`。只检测到文件存在不等于能够调用成功。
- **Anthropic API Key**：用于 Agent 的模型调用。在 `.env` 中填写 `ANTHROPIC_API_KEY=your-anthropic-key`。Agent 当前模型由 [`config.py`](../config.py) 的 `Config.AI_MODEL` 指定，默认 `claude-sonnet-4-5`。

仅填写 Anthropic API Key，不会让普通聊天与日记改为直接调用 Anthropic API；应用仍走 CLI 路径。反过来，仅登录 CLI，也不能代替 Agent 需要的 API Key。不要将 CLI 认证与 API 服务可用性视作同一项检查。

CLI 聊天明确传入本次会话的人设和上下文，不复用 CLI 历史 session。单次聊天最多等待 120 秒；日记 CLI 调用最多等待 30 秒。具体错误会显示在对应页面；目前没有聊天取消按钮。详见[连续聊天与人设](usage-and-storage.md#连续聊天与人设)。

## 什么时候进入 Agent

Agent 初始化成功时，输入中包含 `帮我`、`帮忙`、`设置`、`定一个`、`查询`、`查一下` 或 `搜索` 等配置关键词，会进入 LangGraph 工作流；普通输入走 API / CLI 聊天。关键词列表位于 `Config.AGENT_TRIGGER_KEYWORDS`。

工作流依次理解、规划、执行、反思和回复，当前提供的工具只有获取新闻与设置倒计时，不是通用网页搜索或电脑操作代理。工作流可能进行多次模型请求。只配了 CLI 时，包含这些关键词的输入仍可能进入 Agent 并因缺少 API 凭据失败。

倒计时结束后，桌宠会放大并移动提醒；双击桌宠停止提醒。[动画与提醒行为](usage-and-storage.md#桌面角色与动画)

## 检测到配置，不代表连接已验证

聊天页和设置页会分别显示普通聊天与 Agent 的配置状态。它们只检查变量或本机 CLI 是否存在，不会自动调用模型、检测余额或验证登录。服务是否可达、所选模型是否可用、权限与费用，需由实际使用的服务决定。

应用不承诺免费额度、特定网络环境可达或无需网络代理。仓库的离线检查使用模拟服务，不应据此判断真实模型生成效果。

## 独立的数据目录

不配置时继续使用 `~/.desktop-pet-state.json`。需要隔离运行时，可在 `.env` 中填入绝对目录：

```dotenv
CRITTER_DATA_DIR="/absolute/path/to/critter-data"
```

也支持 `~/...`。目录下使用 `state.json`；现有默认数据不会自动迁移或覆盖。数据目录还可以在启动时指定，其优先级高于 `.env`。迁移前请先阅读[数据位置与恢复说明](usage-and-storage.md#资源与本地数据)。
