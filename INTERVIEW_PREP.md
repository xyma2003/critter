# Critter 项目面试准备

> 适用场景：简历中写了 Critter 个人项目，面试官针对此项目展开提问。  
> 核心策略：把个人项目往"工程判断力"和"技术深度"上引，不要停留在功能演示层面。

---

## Q1：这个项目整体架构是怎样的？为什么这样分层？

*（也可能被问成：你是怎么组织代码结构的？模块之间怎么划分职责？）*

### 面试官想听到的
考察点：**架构表达能力 + 分层设计意识**。想知道你不只是"写了一个项目"，而是有意识地做了设计决策，并且能说清楚为什么这样分。

### 代码中的实际方案

项目分四层：

```
config.py          ← 配置层：主题色、路径常量
data/              ← 持久化层：Repository 封装 JSON 读写
services/          ← 业务服务层：AI 调用、新闻抓取、天气、日记生成
ui/                ← 展示层：两个窗口类 + 五个 Tab
```

**为什么这样分**：这个架构是重构出来的，不是一开始就有的。最初 80% 的代码堆在一个 2000 行的 `panel.py` 里，改一个功能要全文搜索。重构的驱动力是：新增天气服务时发现要在 `panel.py` 里插入大量 HTTP 调用代码，和 UI 逻辑完全混在一起，改不下去了，才把业务逻辑抽到 `services/weather/`，`panel.py` 只调用接口。

**关键约束**：`data/` 层是 UI 不直接碰文件的屏障——所有 JSON 读写必须通过 Repository 类，UI 只调用 `create()`、`update()`、`delete()` 这样的语义方法，不感知文件路径和格式。

### 如何对面试官表述
> "项目分四层：配置、持久化、业务服务、展示。这个架构是重构出来的——最初代码全堆在一个 2000 行的 panel.py 里，新增天气功能时发现 HTTP 调用和 UI 逻辑完全混在一起，改不下去了，才把业务逻辑抽到 services/ 层。分层之后新增功能只需要在对应层加文件，不改已有代码。持久化层的关键设计是 UI 不直接碰文件，所有读写通过 Repository 类封装，上层只调用语义方法。"

### 亮点
- 架构是被真实问题驱动出来的，不是设计驱动
- 分层有明确的边界：UI 不直接碰文件

### 瓶颈
- `MainPanel` 类本身还是一个 God Object，持有了几乎所有 UI 状态
- 没有依赖注入，`panel.py` 直接 import `services/`，替换实现成本较高

### 突出的能力
**架构演化意识** + **分层设计的实际落地**

---

## Q2：你用了哪些设计模式？能结合代码举例吗？

*（也可能被问成：你的代码里有哪些值得说的设计？）*

### 面试官想听到的
考察点：**设计模式的实际应用**。不是让你背书，而是看你能否说清楚在哪个具体问题上用了哪个模式，以及为什么。

### 代码中的实际方案

**工厂模式**：`pipeline/service.py` 风格的初始化——`config.py` 里的 `THEMES` 字典根据 `_theme_mode` 配置动态决定所有 UI 组件的颜色，`th = THEMES[self._theme_mode]` 是每个 build 方法的第一行，UI 组件不感知当前是深色还是浅色主题。

**Repository 模式**：`data/storage/__init__.py` 里的 `StorageRepository` 封装了书签和稍后再看的 CRUD，上层只调用 `add_bookmark()`、`remove_bookmark()`，不知道底层是 JSON 文件。

**状态机**：便签模块的三态管理——`_notes_mode` 取值 `'list'`、`'view'`、`'edit'`、`'readonly'`，每次切换调 `_notes_clear_pane()` 销毁旧容器，工具栏按钮的显隐由当前状态决定，避免了一堆散落的 `if mode == 'edit' and xxx` 条件判断。

**观察者模式（简化版）**：宠物状态（mood/hunger/energy）变化后，UI 主动拉取 `PetStats` 的值更新进度条，而不是 `PetStats` 广播变更。这是个简化版，如果订阅者多了应该改成真正的事件总线。

### 如何对面试官表述
> "用了几个。工厂模式体现在主题切换：THEMES 字典根据当前模式返回所有颜色 token，UI 组件不感知是深色还是浅色，只拿 th['BG_WIN'] 这样的语义 key。Repository 模式体现在持久化层：StorageRepository 封装书签 CRUD，上层只调用语义方法，不感知文件路径。状态机体现在便签模块：三种模式用 _notes_mode 统一管理，切换时先清除旧容器再重建，工具栏按钮由状态决定，不是靠条件判断堆砌。"

### 亮点
- 每个模式都有具体的代码落点，不是泛泛而谈
- 状态机设计有明确的业务语义驱动

### 瓶颈
- 观察者模式是简化版（拉模型），如果状态订阅者增多，每次都要主动拉取，效率较低
- 没有依赖注入，模式的灵活性受限

### 突出的能力
**设计模式的实际应用** + **对简化版和完整版方案的清醒认知**

---

## Q3：便签的状态机是怎么设计的？为什么要分四种模式？

*（也可能被问成：便签的 view/edit 切换是怎么实现的？）*

### 面试官想听到的
考察点：**状态机设计能力**，能否说清楚为什么要分状态，以及每个状态的职责边界。

### 代码中的实际方案

`panel.py` 中 `_notes_mode` 的四态：

```
list     → 卡片网格，显示所有便签
view     → 只读渲染 Markdown，工具栏显示「编辑」按钮
edit     → 编辑原始 Markdown 文本，工具栏显示「保存」按钮
readonly → 日记专用只读，不显示「编辑」按钮
```

**切换逻辑统一入口**：每次切换都先调 `_notes_clear_pane()`，销毁当前内容容器并重置引用，再根据目标模式重建 UI。工具栏三个按钮（保存、编辑、返回）的显隐完全由模式决定：

```python
# view 模式
self._notes_save_btn.pack_forget()
self._notes_edit_btn.pack(side=tk.RIGHT, pady=4)
self._notes_back_btn.pack(side=tk.LEFT, pady=4)

# edit 模式
self._notes_save_btn.pack(side=tk.RIGHT, pady=4)
self._notes_edit_btn.pack_forget()
```

**为什么分四种**：view 和 edit 是两种不同的用户意图——查看时不想误触修改，编辑时需要原始 Markdown 文本；readonly 和 view 的区别是日记不允许用户修改（AI 生成的内容），所以不显示编辑按钮。

### 如何对面试官表述
> "便签有四种模式：列表、只读渲染、编辑原文、日记只读。每次切换都先调 _notes_clear_pane() 清理旧容器，再重建目标模式的 UI，工具栏按钮的显隐完全由当前模式决定，不是靠条件判断堆砌。view 和 edit 分开是因为两种用户意图不同——查看时不想误触修改；readonly 和 view 的区别是日记是 AI 生成的，不允许用户编辑。"

### 亮点
- 状态机有明确的业务语义驱动，不是为了用模式而用
- 切换逻辑有统一入口（`_notes_clear_pane`），不是散落在各处的 `destroy()`

### 瓶颈
- 四种模式的 UI 重建逻辑仍然有重复代码（pane 创建、padx 动态更新），已提取成 `_notes_build_padded_inner()` 辅助方法，但 pane 本身的创建还是重复的
- 状态转换没有校验——理论上可以从 list 直接跳到 readonly，但没有显式的合法转换表

### 突出的能力
**状态机设计** + **复杂 UI 流转的结构化思维**

---

## Q4：AI 流式响应是怎么实现的？

*（也可能被问成：你是怎么调用 Claude 的？流式输出怎么做到实时更新 UI 的？）*

### 面试官想听到的
考察点：**进程间通信 + 流式数据处理**。想知道你理解流式处理的本质，不只是"调了个 API"。

### 代码中的实际方案

`services/ai/__init__.py` 中的调用方式：

```python
proc = subprocess.Popen(
    ['/opt/homebrew/bin/claude', '--print',
     '--output-format', 'stream-json',
     '--include-partial-messages',
     '--verbose',
     '--system-prompt', system],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
```

子线程逐行 `readline()` 解析 NDJSON：
```python
for line in proc.stdout:
    data = json.loads(line)
    if data.get('type') == 'stream_event':
        evt = data.get('event', {})
        if evt.get('type') == 'content_block_delta':
            delta = evt.get('delta', {}).get('text', '')
            root.after(0, lambda d=delta: callback(d))
```

**关键点**：`readline()` 而不是 `communicate()`——`communicate()` 等进程退出才返回全量结果，流式效果没了。`root.after(0, callback)` 把 delta 推给主线程更新气泡 UI，保证线程安全。

**翻译调用**是另一种模式：把所有英文标题按 `1. xxx\n2. xxx` 格式合并成一次调用，用正则 `^\d+\.\s+(.+)` 按编号解析结果，容忍 LLM 偶尔跳行或改变顺序。20 条新闻只有一次 API 往返，而不是 20 次。

### 如何对面试官表述
> "用 subprocess.Popen 开 Claude CLI 子进程，传入 --output-format stream-json 参数，CLI 以 NDJSON 格式流式打印事件到 stdout。子线程逐行 readline() 解析，当 type 是 content_block_delta 时提取 delta.text，通过 root.after(0, callback) 推给主线程更新气泡 UI。关键是用 readline() 不用 communicate()——communicate() 等进程退出才返回全量结果，流式效果没了。本质上和 SSE 是同一个模式，只是传输管道从 HTTP 变成了进程 stdout。"

### 亮点
- 理解流式处理的本质，能类比到 SSE
- 批量翻译的设计体现了成本意识（20 次 → 1 次）

### 瓶颈
- 依赖本地 Claude CLI，CLI 不可用时直接失败，没有 fallback 到 HTTP API 的机制
- 子进程方式无法复用连接，每次对话都要启动新进程，有启动开销

### 突出的能力
**流式数据处理** + **进程间通信** + **成本意识的批处理设计**

---

## Q5：GUI 线程安全是怎么处理的？为什么不能在子线程直接操作 UI？

*（也可能被问成：后台任务怎么更新 UI？你遇到过 tkinter 的线程问题吗？）*

### 面试官想听到的
考察点：**并发理解 + GUI 线程安全意识**。想知道你清楚为什么有这个限制，以及正确的解法。

### 代码中的实际方案

tkinter 只能在主线程操作 UI，这是 Tcl/Tk 的底层限制。跨线程操作 widget 会导致随机崩溃或状态错乱。

项目中所有后台任务（新闻抓取、AI 流式响应、日记生成、天气查询）都跑在 daemon 线程里：

```python
threading.Thread(target=_fetch, daemon=True).start()
```

需要更新 UI 时，通过 `root.after(0, callback)` 把回调提交到主线程的事件循环：

```python
# 子线程里
self.win.after(0, lambda chunk=chunk: self._on_stream_chunk(chunk))
```

`after(0, callback)` 的语义是"在主线程尽快执行"，类似 JavaScript 的 `setTimeout(fn, 0)` 或 Android 的 `runOnUiThread()`。

**静音控制的并发保护**：AI 流式输出期间，如果用户切换 Tab 导致 widget 被销毁，回调里要先检查 `self.win.winfo_exists()` 再操作，避免操作已销毁的 widget。

### 如何对面试官表述
> "tkinter 只能在主线程操作 UI，这是 Tcl/Tk 的底层限制，跨线程操作会随机崩溃。所有后台任务跑在 daemon 线程里，需要更新 UI 时通过 root.after(0, callback) 把回调提交到主线程事件循环。after(0) 的语义是'在主线程尽快执行'，类似 JS 的 setTimeout(fn, 0)。还有一个细节：AI 流式输出期间用户可能切换 Tab 导致 widget 被销毁，回调里要先检查 winfo_exists() 再操作，不然会报错。"

### 亮点
- 理解底层原因（Tcl/Tk 限制），不只是"规则是这样"
- 考虑到 widget 生命周期问题（`winfo_exists()` 检查）

### 瓶颈
- 目前没有统一的"安全 UI 更新"封装，每处都手动 `after(0, ...)`，容易遗漏
- 没有取消机制——如果用户关闭窗口时后台线程还在跑，线程会继续到完成才退出（daemon=True 只在主进程退出时才强制杀死）

### 突出的能力
**并发安全意识** + **GUI 线程模型的深入理解**

---

## Q6：过渡话术（先播"好的让我查一下"）和后台处理是并行的吗？

*（也可能被问成：AI 处理期间用户体验是怎么设计的？）*

### 面试官想听到的
考察点：**并发设计 + 用户体验导向的性能优化**。想知道你是否考虑过感知延迟和实际延迟的区别。

### 代码中的实际方案

`panel.py` 中的 AI 调用流程：先在 UI 上显示"思考中..."的 loading 状态，同时在后台线程启动 Claude CLI 子进程。用户看到 loading 的同时，AI 已经开始处理了。

```python
# 主线程：立刻显示 loading 气泡
self._show_thinking_bubble()

# 后台线程：同时启动 AI 处理
threading.Thread(target=self._stream_pet_ai, args=(msg,), daemon=True).start()
```

**与 Peppr Ava 的对比**：Peppr Ava 是语音系统，可以播放过渡话术"Sure, let me check that for you"来填充等待时间；Critter 是 GUI 应用，用 loading 动画（思考气泡）来填充等待时间。原理相同——都是让用户感知到系统在响应，而不是无声地等待。

**日记生成的并行**：每次打开便签 Tab 时，检查今天是否有日记，没有就后台异步生成，不阻塞 Tab 的渲染。日记生成完毕后通过 `root.after(0, self._notes_refresh_if_list)` 刷新列表。

### 如何对面试官表述
> "AI 处理期间，主线程立刻显示'思考中'的 loading 气泡，后台线程同时启动 Claude CLI 处理。用户看到 loading 的同时，AI 已经在跑了。这和语音系统先播过渡话术的原理一样——都是让用户感知到系统在响应，而不是无声等待。日记生成也是类似的：打开便签 Tab 时立刻渲染已有内容，日记在后台生成，完成后再刷新列表，不阻塞 Tab 的首次渲染。"

### 亮点
- 理解感知延迟和实际延迟的区别
- loading 状态和后台处理并行，是实际落地的用户体验优化

### 瓶颈
- 如果 AI 响应太快（<0.5秒），loading 气泡会闪一下消失，体验略奇怪
- 没有超时控制——如果 Claude CLI hang 住，loading 会一直显示

### 突出的能力
**用户体验导向的并发设计** + **感知延迟优化意识**

---

## Q7：系统怎么处理降级和容错？外部依赖失败了会怎样？

*（也可能被问成：如果 Claude CLI 挂了，应用会崩溃吗？你是怎么处理异常的？）*

### 面试官想听到的
考察点：**降级策略设计 + 容错意识**。想知道你是否考虑过外部依赖失败的情况，以及有没有明确的降级行为。

### 代码中的实际方案

**AI 对话降级**：`_stream_pet_ai()` 里有 `try/except`，子进程启动失败或流式解析出错时，把 `accumulated` 设为 `'呜，出了点小问题：{e}'`，显示在气泡里：

```python
except Exception as e:
    accumulated = f'呜，出了点小问题：{e}'
finally:
    self.win.after(0, lambda: self._on_stream_done(accumulated))
```

**新闻翻译降级**：翻译失败时展示原始英文标题，不阻塞新闻加载。翻译是锦上添花，不是核心路径。

**数据文件降级**：所有 JSON 读取通过 `load_json(path, default)` 封装，任何解析异常返回 `default`（通常是 `[]` 或 `{}`），应用用默认值启动而不是崩溃：

```python
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default
```

**macOS 窗口层级降级**：Objective-C 桥接代码包在 `try/except Exception: pass` 里，系统 API 变化时退化到 tkinter 原生行为，不崩溃。

### 如何对面试官表述
> "有几层降级。AI 调用失败时，try/except 捕获异常，在气泡里显示友好错误文字，不崩溃。新闻翻译失败时显示原始英文标题，翻译是锦上添花不是核心路径。数据文件损坏时 load_json 返回默认值，应用用空状态启动。macOS 窗口 API 调用失败时退化到 tkinter 原生行为。降级的原则是：失败不应该阻断主流程，只影响对应的功能。"

### 亮点
- 降级有明确的原则：失败不阻断主流程
- 每个外部依赖都有独立的降级策略，不是统一的 try/except 吞掉所有错误

### 瓶颈
- 静默失败让用户不知道发生了什么，如果 Claude CLI 未安装，用户发消息才发现报错，而不是启动时就提示
- `load_json` 失败时没有备份损坏文件的机制，用户数据丢失但不知道

### 突出的能力
**降级策略设计** + **防御性编程意识**

---

**追问：数据文件损坏了用默认值启动，用户数据就丢了，这个处理合适吗？**

**代码里只做到了"不崩溃"级别，没做到"可恢复"级别。**

现有方案的问题：`load_json` 异常时静默返回默认值，用户不知道数据丢了，也没有机会恢复。

**理想方案——两步改进：**

**第一步：备份损坏文件**
```python
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        # 备份损坏文件，而不是直接丢弃
        backup_path = path + f'.bak.{int(time.time())}'
        shutil.copy(path, backup_path)
        return default
    except FileNotFoundError:
        return default
```

**第二步：启动时提示用户**
```python
if backup_created:
    self._show_status_bar(f'数据文件损坏，已备份到 {backup_path}，从空状态启动')
```

这样用户知道发生了什么，也有机会手动恢复备份文件。

**对面试官表述：**
> "当前只做到了不崩溃，没做到可恢复。更好的做法是两步：第一步，解析失败时把损坏文件备份为 .bak 而不是直接丢弃；第二步，启动后在 UI 上提示用户'数据文件损坏，已备份到 xxx.bak'，让用户知道发生了什么，也有机会手动恢复。"

### 突出的能力
**容错设计的完整性思考** + **"不崩溃"和"可恢复"的区别意识**

---

## Q8：可观测性是怎么做的？出了问题怎么排查？

*（也可能被问成：你的项目有日志吗？怎么知道线上出了什么问题？）*

### 面试官想听到的
考察点：**可观测性意识**，能否说清楚从问题发现到定位的完整链路。

### 代码中的实际方案

**互动日志**（`pet_log.json`）：记录每次宠物互动（喂食、逗猫、休息）的时间戳和台词，以及每次应用启动的"醒来"记录。这个日志既是用户可见的"互动记录"，也是排查"宠物状态为什么不对"的工具。有去重保护——同一分钟内不重复写醒来记录（防止调试重启刷屏）：

```python
wake_line = f'[{now_hm}] 宠物醒来了，开始新的一天 ✨'
already_woke = self._pet_log_history and self._pet_log_history[-1] == wake_line
if not already_woke:
    self._pet_log_history.append(wake_line)
    save_json(PET_LOG_FILE, self._pet_log_history[-200:])
```

**启动日志**：应用启动时 stdout/stderr 重定向到 `/tmp/critter.log`，后台线程异常会打印在这里。

**异常静默处理**：macOS 桥接、新闻抓取、AI 调用都有 `try/except`，失败时在 UI 上显示友好错误文字。代价是排查问题时需要主动看日志，不会主动暴露。

**内存缓存监控**：`_pet_log_history` 保持最近 200 条，`news_cache.json` 存 `cached_at` 时间戳，可以看出缓存命中情况。

**缺失的部分**：没有 Sentry 或等价的崩溃上报，如果要分发给其他用户，出了问题完全不知道。没有完整的端到端延迟埋点，AI 响应时间只能靠肉眼感知。

### 如何对面试官表述
> "有两层：互动日志记录宠物状态变化，既是用户可见的功能，也是排查状态问题的工具；启动日志重定向到 /tmp/critter.log，后台线程异常会打印在这里。异常静默处理让用户体验好，但排查时需要主动看日志。如果要分发给其他人用，应该加 Sentry 做崩溃上报，否则用户环境出问题完全不知道。"

### 亮点
- 互动日志兼具用户功能和调试工具的双重价值
- 去重保护（同分钟不重复写醒来记录）是被真实问题驱动出来的

### 瓶颈
- 没有崩溃上报机制，分发后无法感知用户环境问题
- 没有性能指标埋点，AI 响应延迟只能靠肉眼感知

### 突出的能力
**可观测性的实际落地** + **从真实 bug 驱动出防御性设计的意识**

---

## Q9：Token 消耗怎么控制？有没有做过成本优化？

*（也可能被问成：你的 AI 调用成本是怎么控制的？）*

### 面试官想听到的
考察点：**成本意识 + 优化能力**，能否说清楚 token 消耗的来源和具体的优化手段。

### 代码中的实际方案

**Token 消耗来源**：
1. AI 对话：每次对话的 system prompt + 历史消息 + 用户输入
2. 新闻翻译：每次刷新新闻的批量翻译调用
3. 日记生成：每天一次，包含宠物状态和互动数据

**已有的优化**：

**批量翻译**：20 条新闻一次调用，而不是 20 次单独调用。按编号格式合并 prompt，正则按编号解析结果，容忍 LLM 改变顺序。

**新闻缓存 TTL**：`news_cache.json` 存 `cached_at` 时间戳，30 分钟内不重新抓取也不重新翻译。避免每次打开新闻 Tab 都消耗 token。

**对话历史管理**：`chat_history.json` 最多保留 50 条，session 切换时不会把所有历史都注入到新 session 的 context 里。

**用户画像压缩**：`user_profile.json` 存储的是提炼后的用户偏好摘要，而不是原始对话记录，注入 system prompt 时 token 消耗可控。

**缺失的部分**：没有 prompt caching（Claude 的 cache_control），重复的 system prompt 部分每次都重新计算，是明显的进步空间。

### 如何对面试官表述
> "主要在三个方向优化。一是批量调用：20 条新闻翻译合并成一次调用，而不是 20 次；二是缓存：新闻有 30 分钟 TTL，不重复翻译；三是历史管理：对话历史最多 50 条，用户画像是压缩后的摘要，不是原始记录。缺失的是 prompt caching——重复的 system prompt 每次都重新计算，如果用 Claude 的 cache_control 把固定部分标记为可缓存，能节省不少 token。"

### 亮点
- 批量翻译是实际落地的成本优化，有具体数字（20 次 → 1 次）
- 理解 prompt caching 的优化方向，说明对 Claude API 有深入了解

### 瓶颈
- 没有 token 用量监控，不知道哪个功能最费 token
- 没有 prompt caching，固定的 system prompt 部分每次都重新计算

### 突出的能力
**成本意识** + **缓存策略的实际落地**

---

## Q10：如果要新增一个"日历"Tab，工作量在哪里？架构支持吗？

*（也可能被问成：你的架构扩展性怎么样？新增功能容易吗？）*

### 面试官想听到的
考察点：**对现有架构扩展性的判断**，能否快速评估新需求的成本，而不是泛泛说"加一个 Tab 就行了"。

### 代码中的实际方案

现有架构对新增 Tab 支持得比较好。需要改动的文件：

1. **`config.py`**：在导航栏配置里加 `'calendar'` 条目，包含图标和标签
2. **`ui/tabs/calendar.py`**：新建 Tab 的 build 函数，返回 `tk.Frame`
3. **`ui/panel.py`**：在 `_build()` 里调用 `calendar.build()`，把返回的 Frame 注册到 `_tab_frames`
4. **`services/calendar/`**：如果有业务逻辑（比如从系统日历读取事件），新建 service 模块

**不需要改**：其他 Tab 的代码、导航切换逻辑（`_switch_tab` 是通用的 `tkraise()` 调用）、数据持久化层。

**真正的工作量**：UI 构建和业务逻辑本身，框架层面的接入成本很低。

**对比重构前**：重构前所有 Tab 代码都在 `panel.py` 里，新增 Tab 要在一个 2000 行文件里找位置插入，改动风险高。现在每个 Tab 是独立文件，新增不影响已有代码。

### 如何对面试官表述
> "架构支持得比较好。新增日历 Tab 只需要改四个地方：config.py 加导航配置、新建 ui/tabs/calendar.py、panel.py 里调用 build 函数并注册、如果有业务逻辑新建 services/calendar/。不需要改其他 Tab 的代码，导航切换逻辑是通用的。最大的工作量在 UI 和业务逻辑本身，框架接入成本很低。这是重构带来的好处——重构前所有 Tab 代码堆在 panel.py 里，新增要在 2000 行文件里找位置插入，风险高。"

### 亮点
- 能具体说出要改哪几个文件，不是泛泛说"加一个 Tab"
- 对比重构前后，说明分层架构的实际收益

### 瓶颈
- `MainPanel` 类仍然是新 Tab 的状态容器，新 Tab 的状态变量会继续堆在 `MainPanel` 上，God Object 问题没有根本解决
- 没有 Tab 的懒加载机制，所有 Tab 在面板初始化时就全部构建，新增 Tab 会增加启动时间

### 突出的能力
**架构扩展性的具体评估** + **重构价值的量化表达**

---

## Q11：如果把 AI 后端从 Claude CLI 换成直接调 OpenAI API，怎么改？

*（也可能被问成：你的 AI 调用耦合严重吗？换一个模型要改多少代码？）*

### 面试官想听到的
考察点：**服务层抽象能力 + 对依赖替换成本的评估**。想知道你能说清楚现在的耦合点在哪，以及最小改动路径。

### 代码中的实际方案

目前 Claude CLI 的调用逻辑集中在 `services/ai/__init__.py`。AI 对话和翻译都走这里，`panel.py` 只调用 `services/ai` 暴露的函数，不直接操作 subprocess。

**需要改的**：`services/ai/__init__.py` 里的调用方式——从 `subprocess.Popen` 开子进程改成 `openai.AsyncOpenAI().chat.completions.create(stream=True)`，流式解析从读 stdout NDJSON 改成消费 stream 对象的 delta。

**不需要改的**：`panel.py` 里的 `_on_stream_chunk` 和 `_on_stream_done` 回调——它们只关心"收到一个文本 delta"这个事件，不关心 delta 从哪来。

**现有抽象的有效性**：service 层把调用方式封装了，UI 层和 AI 提供商解耦了。如果做得更干净，可以在 `services/ai/` 里定义一个 `AIService` 抽象接口，`ClaudeService` 和 `OpenAIService` 分别实现，通过工厂函数根据配置选择——这样连 `services/ai/__init__.py` 的调用代码都不用改，只改工厂函数里的选择逻辑。

### 如何对面试官表述
> "改动集中在 services/ai/__init__.py，把 subprocess.Popen 改成 openai SDK 的流式调用，流式解析从读 stdout NDJSON 改成消费 stream delta。panel.py 里的 _on_stream_chunk 和 _on_stream_done 回调不需要改，它们只关心'收到 delta'这个事件，不感知来源。现有的 service 层抽象是有效的。如果要做得更干净，可以定义 AIService 抽象接口，Claude 和 OpenAI 各实现一个，工厂函数根据配置选择，这样提供商切换不需要改任何业务代码。"

### 亮点
- 能具体说出改动范围，而不是"改一下就好了"
- 知道现有抽象的边界在哪里，以及更完整的抽象方向

### 瓶颈
- 目前 `services/ai/__init__.py` 没有定义接口，只有一种实现，替换时需要改实现代码
- 翻译的批处理格式（编号 prompt）是 Claude 特定的 prompt 设计，换模型时 prompt 也要调整

### 突出的能力
**服务层抽象能力** + **依赖替换成本的精确评估**

---

## Q12：主题切换是怎么实现的？切换时为什么不重建 UI？

*（也可能被问成：你的深色/浅色主题是怎么做到实时切换的？`_recolor_widget` 是干什么的？）*

### 面试官想听到的
考察点：**UI 状态管理 + 性能意识**。想知道你理解"重建"和"就地更新"的 trade-off，以及颜色映射的具体实现。

### 代码中的实际方案

`_apply_theme()` 的核心是**预计算颜色映射表**，然后递归遍历整棵 widget 树：

```python
def _apply_theme(self, mode):
    self._theme_mode = mode
    th = THEMES[mode]
    # 预计算：把所有主题的颜色值 → 目标主题颜色值
    self._color_bg_map = {}
    self._color_fg_map = {}
    for t in THEMES.values():           # 遍历 light 和 dark 两套
        self._color_bg_map[t['BG_WIN']] = th['BG_WIN']
        self._color_bg_map[t['BG_CARD']] = th['BG_CARD']
        # ... 所有 bg key
        self._color_fg_map[t['FG_MAIN']] = th['FG_MAIN']
        # ... 所有 fg key
    self._recolor_widget(self.win, th)  # 递归遍历
```

`_recolor_widget()` 对每个 widget：
1. 读出当前 `bg` 颜色值
2. 查 `_color_bg_map`，如果是已知主题色就替换成目标主题色
3. 对 Label/Text/Canvas 同样处理 `fg`、`highlightbackground`
4. 对 Text widget 额外更新 `insertbackground`（光标色）和 `selectbackground`
5. 递归处理所有子 widget

**为什么不重建 UI**：重建整个面板需要销毁并重新创建数百个 widget，会有明显闪烁，而且需要恢复所有状态（当前 Tab、输入框内容、滚动位置）。就地更新只改颜色属性，不改结构，无闪烁。

**预计算的意义**：如果不预计算，`_recolor_widget` 每次都要判断"当前颜色是哪个主题的哪个 key"，复杂度高。预计算后只需一次 dict 查找，O(1)。

### 如何对面试官表述
> "主题切换不重建 UI，而是递归遍历整棵 widget 树就地更新颜色。核心是预计算一张颜色映射表：把所有已知主题的颜色值映射到目标主题的对应颜色值，这样对每个 widget 只需读出当前颜色、查一次 dict、写回新颜色。不重建的原因是重建会有闪烁，而且要恢复所有 UI 状态成本高。预计算是为了避免在递归里做复杂的颜色识别，降到 O(1) 查找。"

### 亮点
- 预计算颜色映射表，把递归里的颜色识别降到 O(1)
- 就地更新避免闪烁，比重建 UI 体验好

### 瓶颈
- 递归遍历整棵 widget 树，widget 数量多时有性能开销（虽然实际上感知不到）
- 依赖"widget 当前颜色一定是某个主题色"这个假设——如果某个 widget 用了硬编码颜色（比如 `#ff0000`），切换主题时不会被更新

### 突出的能力
**UI 状态就地更新** + **预计算优化思维**

---

**追问：如果某个 widget 的颜色是硬编码的（不在 THEMES 里），切换主题后会怎样？**

会被遗漏，保持原来的硬编码颜色，出现"主题不一致"的视觉 bug。

**代码中的实际情况**：`_RANK_COLORS = ['#ef5350', '#ff7043', '#ffa726']`（新闻排名颜色）是硬编码的，不在 THEMES 里，切换主题后这三个颜色不会变。这是有意为之——排名颜色是语义色（红/橙/黄代表热度），不随主题变化。

**真正的风险**：如果开发者不小心在某个地方用了 `bg='#1e1e1e'` 而不是 `th['BG_CONTENT']`，这个 widget 切换到浅色主题后背景还是深色，但文字变成了浅色主题的深色文字，对比度可能变成黑字黑底，完全看不见。

**防御方案**：在 `_recolor_widget` 里加一个"未命中"日志：
```python
if cur_bg and cur_bg not in all_bgs and not cur_bg.startswith('system'):
    print(f'[theme] WARNING: widget {widget.winfo_class()} has untracked bg {cur_bg!r}')
```
开发时开启，能快速发现遗漏的硬编码颜色。

**突出的能力**：**对设计约束的清醒认知** + **防御性调试手段**

---

## Q13：用户画像（user_profile.json）是怎么提取和使用的？有没有并发问题？

*（也可能被问成：你说 AI 能记住用户信息，这是怎么实现的？每次对话都会更新吗？）*

### 面试官想听到的
考察点：**异步任务设计 + 数据一致性**。想知道你是否意识到并发写同一个文件的风险，以及提取逻辑是怎么设计的。

### 代码中的实际方案

**提取时机**：每次对话结束（`_on_stream_done`）后，如果 `_profile_enabled` 为 True，异步启动 `_extract_profile_async`：

```python
threading.Thread(
    target=self._extract_profile_async,
    args=(last_user, final_text),
    daemon=True
).start()
```

**提取逻辑**（`_extract_profile_async`）：
1. 读取现有 `user_profile.json`（`existing`）
2. 把 `existing` 序列化成 JSON 字符串作为"已有画像"注入 prompt
3. 让 Claude 从本轮对话中提取：`name`（用户名字）、`pet_nickname`（用户给宠物的称呼）、`notes`（其他自我介绍）
4. 解析 Claude 返回的 JSON，**合并**到 `existing`：name/pet_nickname 直接覆盖，notes 追加去重
5. 写回 `user_profile.json`

**注入时机**：每次 `_stream_pet_ai` 时，读取 `user_profile.json` 注入 system prompt：
```python
profile = load_json(USER_PROFILE_FILE, {})
if profile.get('name'):
    system += f'用户名字叫{profile["name"]}。'
```

**并发问题**：存在 race condition。如果用户连续快速发两条消息，两个提取线程并发运行：
1. 线程 A 读 `existing`（空）
2. 线程 B 读 `existing`（空）
3. 线程 A 提取到 `name="小明"`，写入
4. 线程 B 提取到 `notes=["喜欢猫"]`，写入——**覆盖了线程 A 写的 name**

### 如何对面试官表述
> "用户画像提取是对话结束后 fire-and-forget 的异步任务，让 Claude 从本轮对话里提取用户名字、对宠物的称呼、自我介绍信息，合并到 user_profile.json。注入时每次对话开始前读取这个文件，拼进 system prompt，让 AI 能认出老用户。有一个真实的并发问题：用户快速连发两条消息，两个提取线程并发读-改-写同一个文件，后写的会覆盖先写的结果。修复方案是加文件级锁，或者改成单线程队列处理所有提取请求。"

### 亮点
- 提取逻辑的 merge 策略有考虑：notes 追加去重而不是覆盖，避免信息丢失
- 主动识别并发问题，不等面试官追问

### 瓶颈
- 没有文件锁，并发写存在 race condition
- 每次对话都调用一次 Claude 做提取，即使对话里没有任何个人信息也会调用，浪费 token
- 提取质量完全依赖 LLM，可能误提取（把"我的猫叫小白"识别成用户名字）

### 突出的能力
**异步任务设计** + **并发写的风险识别**

---

**追问：怎么修复这个并发写问题？**

**两种方案：**

**方案一：threading.Lock**
```python
self._profile_lock = threading.Lock()

def _extract_profile_async(self, user_text, pet_reply):
    with self._profile_lock:          # 同一时刻只有一个线程在读-改-写
        existing = load_json(USER_PROFILE_FILE, {})
        # ... 提取和合并逻辑 ...
        save_json(USER_PROFILE_FILE, existing)
```
简单直接，但锁住的时间包含 Claude 调用（10-30 秒），后续提取请求会排队等待很久。

**方案二：单线程队列（更好）**
```python
import queue
self._profile_queue = queue.Queue()

# 启动一个专用的提取线程
def _profile_worker():
    while True:
        user_text, pet_reply = self._profile_queue.get()
        self._do_extract_profile(user_text, pet_reply)

threading.Thread(target=_profile_worker, daemon=True).start()

# 对话结束时入队，不直接启动线程
def _on_stream_done(self, final_text):
    if self._profile_enabled:
        self._profile_queue.put((self._last_user_text, final_text))
```
好处：提取串行执行，不存在并发写；队列天然缓冲，不丢失任何提取请求；Claude 调用在专用线程里，不阻塞主流程。

**对面试官表述：**
> "方案一是加 threading.Lock，但锁住的时间包含 Claude 调用，等待时间太长。更好的方案是单线程队列：启动一个专用的 profile_worker 线程，对话结束时把 (user_text, reply) 入队，worker 串行处理，不存在并发写，也不阻塞主流程。"

**突出的能力**：**并发控制的方案选择** + **队列模式的实际应用**

---

## Q14：聊天气泡是怎么渲染的？为什么用 Canvas 而不是 Label？

*（也可能被问成：你的圆角气泡是怎么实现的？流式更新时气泡怎么动态改变大小？）*

### 面试官想听到的
考察点：**自定义渲染能力**。想知道你理解 tkinter 渲染的底层，以及为什么 Label 无法满足需求。

### 代码中的实际方案

`_rounded_bubble()` 的实现：

1. **测量文字尺寸**：创建一个临时 Label，`update_idletasks()` 强制布局，读取 `winfo_reqwidth()` 和 `winfo_reqheight()`，然后立刻 `destroy()`
2. **创建 Canvas**：宽高 = 文字尺寸 + padding，`highlightthickness=0, bd=0` 去掉边框
3. **绘制圆角矩形**：用 4 个 `create_arc`（四个角）+ 2 个 `create_rectangle`（横竖填充）拼出圆角矩形，统一打 `'bubble_bg'` tag
4. **叠加文字**：`create_text` 在 Canvas 上绘制文字，保存 `_text_id`

**为什么不用 Label**：Label 的 `bg` 是矩形，无法做圆角。虽然可以用 Frame 套 Label 加 `highlightbackground` 模拟边框，但无法做圆角填充。

**流式更新**（`_update_bubble`）：
```python
def _update_bubble(self, canvas, new_text):
    tw, th_h = canvas._measure(new_text)    # 重新测量
    w = tw + canvas._bubble_padx * 2
    h = th_h + canvas._bubble_pady * 2
    canvas.configure(width=w, height=h)      # 调整 Canvas 尺寸
    canvas.delete('bubble_bg')               # 删除旧圆角矩形
    self._draw_rounded_rect(...)             # 重绘
    canvas.tag_raise(canvas._text_id)        # 文字层置顶
    canvas.itemconfigure(canvas._text_id, text=new_text)  # 更新文字
```

每次收到流式 delta 都调用 `_update_bubble`，Canvas 动态扩大，气泡跟着文字增长。

### 如何对面试官表述
> "气泡用 Canvas 而不是 Label，因为 Label 的背景只能是矩形，无法做圆角。Canvas 可以用 create_arc 和 create_rectangle 拼出圆角矩形，再用 create_text 叠加文字。流式更新时，每次收到 delta 就重新测量文字尺寸、调整 Canvas 宽高、重绘圆角矩形，气泡跟着文字内容动态增长。测量文字尺寸的方法是创建一个临时 Label，强制布局后读取 reqwidth/reqheight，然后立刻销毁。"

### 亮点
- 理解 tkinter Canvas 的绘图模型（tag 系统、层叠顺序）
- 流式更新时气泡动态扩大，不是等全部完成才渲染

### 瓶颈
- 每次流式 delta 都调用 `_measure`（创建临时 Label），高频更新时有性能开销
- `_measure` 依赖 `update_idletasks()`，在某些情况下可能返回 0（widget 还没映射到屏幕时）

### 突出的能力
**自定义渲染实现** + **流式 UI 更新的动态布局**

---

**追问：每次 delta 都创建临时 Label 来测量，这个开销合理吗？有没有更好的方案？**

**代码里的实际频率**：Claude 流式输出约每 50-200ms 一个 delta，每次都创建+销毁一个 Label，频率不算高，实际感知不到性能问题。

**但从工程角度看是可以优化的**：

**方案：用 `font.measure()` 替代临时 Label**
```python
from tkinter import font as tkfont

def _measure_text(self, text, font_spec, max_wrap):
    f = tkfont.Font(family=font_spec[0], size=font_spec[1])
    lines = text.split('\n')
    # 考虑 wraplength 做换行计算
    max_line_w = min(max(f.measure(line) for line in lines), max_wrap)
    line_h = f.metrics('linespace')
    # 估算行数（简化：不考虑单词边界换行）
    total_h = sum(
        math.ceil(f.measure(line) / max_wrap) * line_h if f.measure(line) > max_wrap else line_h
        for line in lines
    )
    return max_line_w, total_h
```

好处：不创建 widget，纯计算，开销更低。代价：换行计算是近似的（不考虑单词边界），可能和 tkinter 实际换行位置有 1-2px 偏差。

**对面试官表述：**
> "当前用临时 Label 测量，频率约每 100ms 一次，实际感知不到性能问题。但可以用 tkfont.Font 的 measure() 方法替代，纯计算不创建 widget，开销更低。代价是换行计算是近似的，不考虑单词边界，可能有 1-2px 偏差。对聊天气泡这种场景，近似值完全够用。"

**突出的能力**：**性能权衡的量化分析** + **tkinter 字体 API 的深入了解**

---

## Q15：宠物状态（mood/hunger/energy）的衰减逻辑是怎么设计的？mood 为什么不单独衰减？

*（也可能被问成：宠物的三个数值是怎么联动的？喂食/逗猫/休息对数值的影响是怎么设计的？）*

### 面试官想听到的
考察点：**游戏机制设计 + 数值系统建模**。想知道你对状态联动有没有设计意图，而不是随便填了几个数字。

### 代码中的实际方案

`data/pet/__init__.py` 中的数值系统：

**衰减规则**（每 10 分钟）：
```python
HUNGER_DECAY = 6    # 饱食度 -6
ENERGY_DECAY = 4    # 精力 -4
# mood 不单独衰减，由 hunger 和 energy 共同决定
self.mood = self._clamp(max(20.0, self.mood - 3))  # 但 decay 时也小幅下降
```

**初始化时**：`mood = hunger * 0.5 + energy * 0.5`（加权平均），但保存后 mood 独立存储，后续不再用公式计算，只靠互动和衰减更新。

**互动对数值的影响**：
- `feed()`：hunger +35，energy +10（吃饱了有精神）
- `play()`：hunger -10，energy -15，**mood +20**（玩耍直接拉心情，不依赖 hunger/energy）
- `rest()`：energy +40（只恢复精力）
- `on_chat()`：mood +8（对话让宠物开心）
- `pet()`：mood +10，hunger -5（抚摸让宠物开心，但消耗一点注意力）

**为什么 mood 不单独衰减**：mood 是"情感状态"，不像饥饿感那样有明确的物理规律，单独衰减会显得机械。设计意图是：mood 通过互动（聊天、逗猫、抚摸）提升，通过 hunger/energy 低落时被拖低（`decay` 时小幅下降），体现"饿了/累了就不开心"的自然联动。

**system_prompt_hint()**：mood 值直接影响 AI 的说话风格，mood >= 80 时"活泼开朗，喜欢叠词"，mood < 20 时"说话有气无力，会撒娇"。这是数值系统和 AI 人格的结合点。

### 如何对面试官表述
> "三个数值有不同的物理语义：hunger 和 energy 有自然衰减，mood 没有单独衰减规律，而是通过互动提升、通过 hunger/energy 低落时被拖低。设计意图是让宠物行为符合直觉——饿了累了就不开心，但心情可以通过聊天和逗猫独立提升，不完全依赖饱食和精力。最有意思的是 mood 值会注入到 AI 的 system prompt 里，直接改变宠物的说话风格，让数值系统和 AI 人格形成闭环。"

### 亮点
- 数值联动有设计意图，不是随机填数字
- mood 和 AI system prompt 的结合是数值系统和 AI 人格的闭环设计

### 瓶颈
- 数值都是线性变化，没有边际效益（第 10 次喂食和第 1 次效果完全一样）
- `play()` 消耗 energy 但 mood +20，存在"一直逗猫刷满 mood 但 energy 归零"的极端情况
- 衰减参数（6、4、3）是硬编码，不同宠物性格应该有不同的衰减速率

### 突出的能力
**数值系统建模** + **AI 人格与游戏机制的结合设计**

---

## Q16：便签的 ID 用时间戳，如果两个便签在同一秒创建会怎样？

*（也可能被问成：你的数据 ID 是怎么生成的？有没有碰撞风险？）*

### 面试官想听到的
考察点：**ID 生成策略的工程意识**。这是一个细节题，想知道你是否想过 ID 碰撞的问题，以及你怎么评估风险。

### 代码中的实际方案

`services/notes/__init__.py`：
```python
def create(content, title=''):
    now = int(time.time())   # Unix 时间戳，精度：秒
    note = {'id': now, ...}
```

`services/chat_history/__init__.py`：
```python
sid = int(time.time() * 1000)   # 毫秒时间戳
```

**碰撞分析**：
- 便签 ID 精度是**秒**，同一秒内创建两个便签会产生相同 ID
- `save_all()` 直接追加，不检查 ID 唯一性，两个便签会共存于列表中，但 ID 相同
- `update()` 和 `delete()` 用 `n['id'] == note_id` 匹配，会同时操作两个 ID 相同的便签——删除时两个都删，更新时两个都改

**实际风险**：用户手速再快也不可能在 1 秒内连续新建两个便签（需要填内容后点保存），所以这个 bug 在正常使用中几乎不会触发。但这是一个真实存在的设计缺陷。

**聊天 session** 用毫秒时间戳，碰撞概率低得多，基本可以忽略。

### 如何对面试官表述
> "便签 ID 用秒级时间戳，理论上同一秒内创建两个便签会 ID 碰撞。碰撞后 update 和 delete 会同时操作两条记录，因为匹配条件是 id 相等。实际风险很低——用户不可能在 1 秒内连续创建两个便签，所以没有在实际使用中触发过。修复方案是把 ID 改成 `int(time.time() * 1000000)`（微秒）或者 `uuid.uuid4().hex`，彻底消除碰撞可能。聊天 session 用的是毫秒时间戳，碰撞概率已经很低了。"

### 亮点
- 主动分析碰撞场景（update/delete 的影响），不只说"可能碰撞"
- 区分实际风险和理论风险，有工程判断

### 瓶颈
- 秒级时间戳作为 ID 是明显的设计缺陷，应该在设计时就用更高精度或 UUID

### 突出的能力
**ID 生成策略的工程意识** + **风险量化评估**

---

## Q17：书签的排序是怎么做的？`_parse_saved_at` 为什么要支持多种时间格式？

*（也可能被问成：你的 StorageRepository 里有什么值得说的设计？）*

### 面试官想听到的
考察点：**防御性编程 + 数据兼容性意识**。想知道你是否理解"历史数据格式不统一"这类真实工程问题，以及如何处理。

### 代码中的实际方案

`data/storage/__init__.py` 中的 `_parse_saved_at`：

```python
_SAVED_AT_FORMATS = ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S')

def _parse_saved_at(item):
    raw = item.get('saved_at', '')
    for fmt in _SAVED_AT_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    print(f'[storage] WARNING: unparseable saved_at ...', file=sys.stderr)
    return datetime.fromtimestamp(0, tz=timezone.utc)   # epoch 兜底
```

**为什么支持三种格式**：`saved_at` 字段是字符串，在不同版本的代码里可能用了不同的 `strftime` 格式——早期可能没有微秒（`%Y-%m-%dT%H:%M:%S`），后来加了微秒（`%Y-%m-%dT%H:%M:%S.%f`），或者用了空格分隔而不是 T（`%Y-%m-%d %H:%M:%S`）。已经写入磁盘的历史数据不会自动迁移，所以读取时需要兼容所有曾经用过的格式。

**epoch 兜底**：解析失败时返回 `datetime.fromtimestamp(0)`（1970-01-01），这样排序时这条记录会排到最后，不会崩溃，只是顺序可能不对，并且打印警告方便排查。

**`list_items` 的排序**：`sorted(items, key=_parse_saved_at, reverse=True)`，按保存时间倒序，最新的排最前面。

### 如何对面试官表述
> "saved_at 支持三种格式是因为历史数据格式不统一——不同版本的代码可能用了不同的 strftime 格式，已经写入磁盘的数据不会自动迁移，读取时必须兼容。解析失败时返回 epoch 兜底，这样排序不会崩溃，只是这条记录会排到最后，同时打印警告方便排查。这是一个典型的'历史包袱'问题——如果一开始就用 Unix 时间戳整数而不是时间字符串，就不会有这个问题。"

### 亮点
- 理解"历史数据兼容"是真实工程中的常见问题
- epoch 兜底而不是抛异常，降级处理而不是崩溃

### 瓶颈
- 字符串时间戳本身就是一个设计问题，应该用 Unix 时间戳整数，既无格式问题又节省存储

### 突出的能力
**数据兼容性意识** + **防御性降级处理**

---

## Q18：懒加载是怎么做的？为什么新闻和天气 Tab 不在面板初始化时就加载数据？

*（也可能被问成：面板打开时所有 Tab 的数据都会立刻加载吗？）*

### 面试官想听到的
考察点：**懒加载设计 + 启动性能意识**。想知道你是否有意识地控制启动时的资源消耗。

### 代码中的实际方案

`_switch_tab()` 里的懒加载逻辑：

```python
if key == 'news':
    if not self._news_loaded:
        self._news_loaded = True          # 标记已触发，防止重复加载
        self._load_news_async(force=False) # 后台加载，不阻塞

if key == 'weather':
    if not self._weather_loaded:
        self._weather_loaded = True
        self._weather_cities = load_json(WEATHER_FILE, [])
        # ... 初始化城市列表 + 后台拉取天气
    elif self._weather_selected:
        self._load_weather_async(self._weather_selected, force=True)  # 每次切换都刷新
```

**设计意图**：
- 面板初始化时只构建 UI 骨架（`_build_xxx_tab` 只创建 widget，不发网络请求）
- 数据加载推迟到用户第一次切换到对应 Tab 时触发
- 新闻只加载一次（有 `_news_loaded` 标记），之后靠定时刷新；天气每次切换都刷新（用户期望看到最新数据）

**启动性能**：如果启动时就加载所有数据，面板打开会有明显延迟（新闻抓取 + 翻译需要 5-10 秒）。懒加载让面板秒开，用户切到新闻 Tab 时才开始加载，加载期间显示 loading 状态。

**对比**：`_build_notes_tab` 里的日记生成是另一种懒加载——不是等用户切换，而是切换到便签 Tab 时后台检查并生成，不阻塞 Tab 渲染。

### 如何对面试官表述
> "新闻和天气数据是懒加载的——面板初始化时只建 UI 骨架，不发任何网络请求。用 _news_loaded 和 _weather_loaded 两个 flag 控制，用户第一次切换到对应 Tab 时才触发加载。这样面板打开是秒开的，不会因为网络请求而卡顿。新闻加载一次后靠定时刷新，天气每次切换都刷新，因为用户期望看到最新数据。"

### 亮点
- 懒加载 flag 防止重复触发
- 新闻和天气的刷新策略不同，体现了对用户期望的细致考虑

### 瓶颈
- 所有 Tab 的 UI 骨架在面板初始化时全部构建，如果 Tab 数量很多，初始化时间会增加
- 天气每次切换都刷新，如果用户频繁切换 Tab，会产生大量重复的 HTTP 请求

### 突出的能力
**启动性能优化** + **懒加载的差异化策略设计**

---

**追问：天气每次切换都刷新，如果用户在 10 秒内切换了 5 次，会发 5 次请求吗？**

**代码里有部分保护**：`_weather_fetching` 是一个 `set`，记录正在拉取的城市：

```python
def _load_weather_async(self, city, force=True):
    if city in self._weather_fetching:
        self._weather_status.configure(text='正在刷新...')
        return                           # 已在拉取中，跳过
    self._weather_fetching.add(city)
    # ... 后台线程拉取，完成后 _weather_fetching.discard(city)
```

所以如果上一次请求还没完成，再次切换 Tab 不会重复发请求。**但如果上一次请求已经完成（比如网络很快，1 秒内返回），再次切换就会再发一次**。

**更完整的防抖方案**：加一个最小刷新间隔，比如 30 秒内不重复刷新同一城市：

```python
self._weather_last_fetch: dict[str, float] = {}  # city -> timestamp

def _load_weather_async(self, city, force=False):
    if city in self._weather_fetching:
        return
    last = self._weather_last_fetch.get(city, 0)
    if not force and time.time() - last < 30:    # 30 秒内不重复刷新
        return
    self._weather_last_fetch[city] = time.time()
    # ...
```

**对面试官表述：**
> "有一层保护：_weather_fetching 记录正在拉取的城市，请求未完成时不重复发。但请求完成后再切换还是会重发。更完整的方案是加最小刷新间隔——30 秒内不重复刷新同一城市，只有 force=True（用户主动点刷新）才绕过这个限制。"

**突出的能力**：**防抖设计的完整性思考** + **主动发现代码里的保护边界**

---

## Q19：聊天 session 的持久化是怎么做的？session 标题是怎么生成的？有没有内存泄漏风险？

*（也可能被问成：历史对话是怎么保存的？重启后能恢复吗？）*

### 面试官想听到的
考察点：**数据持久化设计 + 内存管理意识**。想知道你是否考虑过内存中 session 数量无限增长的问题。

### 代码中的实际方案

**持久化时机**：用户点"← 主页"时调用 `_save_current_session()`，从 `_chat_inner` 的 widget 树里**逆向提取**气泡文字：

```python
for row in self._chat_inner.winfo_children():
    for child in row.winfo_children():
        if child.winfo_class() == 'Canvas' and hasattr(child, '_text_id'):
            text = child.itemcget(child._text_id, 'text')
            role = 'user' if child._bubble_bg == th['FG_ACCENT'] else 'pet'
            bubbles.append((role, text))
```

**角色判断**：通过气泡背景色区分 user（accent 色）和 pet（card 色）。这是一个隐式约定，如果主题色变了，判断可能出错。

**标题生成**：取第一条 user 消息的前 20 字：
```python
for role, text in bubbles:
    if role == 'user':
        sess['title'] = text[:20] + ('…' if len(text) > 20 else '')
        break
```

**磁盘限制**：`chat_history_service.save_session()` 最多保留 50 条，超出时删最旧的。

**内存泄漏风险**：`self._chat_sessions` 是内存里的列表，整个应用生命周期内只增不减（没有从内存里删除 session 的逻辑），只有磁盘有 50 条上限。如果用户长时间不重启，`_chat_sessions` 会持续增长。但每个 session 的 `bubbles` 只在保存时填充，平时是空列表，实际内存占用不大。

### 如何对面试官表述
> "session 在用户返回主页时保存，从 widget 树里逆向提取气泡文字，通过气泡背景色区分角色。标题取第一条用户消息前 20 字。磁盘有 50 条上限，超出删最旧的。有一个内存问题：_chat_sessions 在内存里只增不减，应用运行时间越长列表越大。不过每个 session 的 bubbles 只在保存时填充，平时是空列表，实际内存占用可控。如果要彻底修复，可以给内存列表也加上限，比如只在内存里保留最近 20 条。"

### 亮点
- 主动识别内存只增不减的问题
- 区分"理论泄漏"和"实际影响"，有工程判断

### 瓶颈
- 通过气泡背景色判断角色是隐式约定，脆弱——主题切换时 `th['FG_ACCENT']` 变了，但已渲染的气泡颜色还是旧的，判断会出错
- 从 widget 树逆向提取数据是反模式，正确做法是维护独立的数据结构，UI 只负责展示

### 突出的能力
**内存管理意识** + **反模式识别（从 widget 提取数据）**

---

**追问：从 widget 树逆向提取数据，你说这是反模式，怎么改？**

**问题的本质**：UI 是数据的视图，不应该是数据的唯一来源。现在 session 的"真实数据"只存在于 Canvas widget 里，如果 widget 被销毁了（比如切换 Tab），数据就丢了。

**正确方案：维护独立的消息列表**

```python
# _switch_to_chat 时初始化
self._current_messages: list[tuple[str, str]] = []  # [(role, text), ...]

# _add_chat_bubble 时同步写入
def _add_chat_bubble(self, role, text):
    self._current_messages.append((role, text))
    # ... 渲染 widget

# _save_current_session 时直接用列表，不从 widget 提取
def _save_current_session(self):
    sess['bubbles'] = self._current_messages
    # 不需要遍历 widget 树
```

这样 `_save_current_session` 只需要读内存列表，不依赖 widget 是否存在，也不依赖气泡颜色来判断角色。

**对面试官表述：**
> "修法是维护一个独立的 _current_messages 列表，每次 _add_chat_bubble 时同步写入。保存时直接读列表，不遍历 widget 树，不依赖气泡颜色判断角色。UI 只负责展示，不是数据的来源。"

**突出的能力**：**数据与视图分离的架构意识** + **反模式的识别和重构方向**

---

## Q20：`_start_stats_decay` 是怎么实现的？为什么不用 `threading.Timer` 而用 `win.after`？

*（也可能被问成：宠物状态的定时衰减是怎么驱动的？）*

### 面试官想听到的
考察点：**tkinter 定时器机制的深入理解**，以及为什么 GUI 应用里不应该用 `threading.Timer`。

### 代码中的实际方案

在 `_build()` 末尾调用 `_start_stats_decay()`，实现为递归 `after` 调用：

```python
def _start_stats_decay(self):
    if self._decay_running:
        return
    self._decay_running = True

    def _tick():
        if not (self.win and self.win.winfo_exists()):
            self._decay_running = False
            return
        self.stats.decay()           # 数值衰减
        self._sync_pet_ui()          # 更新进度条 UI
        self.win.after(PetStats.DECAY_INTERVAL_MS, _tick)  # 10分钟后再次调用

    _tick()
```

**为什么用 `win.after` 而不是 `threading.Timer`**：
- `threading.Timer` 在子线程里执行回调，回调里调用 `_sync_pet_ui()` 更新 UI 会跨线程，违反 tkinter 单线程约束
- `win.after` 在主线程的事件循环里执行，天然线程安全
- `win.after` 会在窗口存在时才执行，可以用 `winfo_exists()` 检查后安全退出，`threading.Timer` 无法感知窗口生命周期

**`_decay_running` flag 的作用**：防止多次调用 `_start_stats_decay` 导致多个并行的衰减循环（比如面板关闭后重新打开时 `_build()` 再次调用）。

### 如何对面试官表述
> "定时衰减用 win.after 递归调用而不是 threading.Timer，原因是 after 在主线程事件循环里执行，可以直接更新 UI；Timer 在子线程里执行，更新 UI 会跨线程，违反 tkinter 约束。after 还能通过 winfo_exists() 感知窗口生命周期，窗口销毁时自然停止。_decay_running flag 防止面板重新打开时启动多个并行的衰减循环。"

### 亮点
- 理解 `win.after` 和 `threading.Timer` 的本质区别（主线程 vs 子线程）
- `_decay_running` 防止重复启动，是真实 bug 的防御

### 瓶颈
- 面板关闭（`win.withdraw`）后 `after` 回调仍在运行，只是不可见——如果用户长时间不打开面板，宠物数值仍然在衰减，这是符合设计意图的，但要注意 `after` 不会自动停止
- 10 分钟的间隔是固定的，不能动态调整（比如用户设置"快速模式"）

### 突出的能力
**tkinter 定时器机制的深入理解** + **GUI 线程安全的具体应用**

---

## 速查：关键技术词汇对照

| 功能 | 技术实现 | 关键词 |
|------|----------|--------|
| AI 流式对话 | subprocess.Popen + NDJSON readline() | 进程通信、流式处理、SSE |
| GUI 线程安全 | daemon thread + `root.after(0, callback)` | 主线程事件循环、线程安全 |
| 窗口常驻顶层 | ctypes + Objective-C runtime + 2s 定时重置 | 跨语言调用、平台 API、优雅降级 |
| Markdown 渲染 | tkinter Text tag 系统（tag_configure + insert） | 富文本、零依赖 |
| 新闻批量翻译 | 编号格式 prompt + 正则按编号解析 | Prompt Engineering、批处理、容错解析 |
| 便签状态机 | `_notes_mode` 四态 + `_notes_clear_pane()` 统一入口 | 状态机、关注点分离 |
| 主题切换 | `THEMES` 字典 + `th = THEMES[mode]` 语义 key | 工厂模式、配置驱动 |
| 持久化封装 | Repository 类 + `load_json(path, default)` | Repository 模式、防御性编程 |
| 后台任务 | daemon thread + `root.after` 回调 | 并发模型、线程安全 |
| 内存缓存 | `_pet_log_history` + 新闻 30min TTL | 读多写少、缓存策略 |
| AI 降级 | try/except + 友好错误文字 | 容错设计、优雅降级 |
| 感知延迟优化 | loading 气泡与 AI 处理并行 | 并发设计、用户体验 |
| 主题切换 | 预计算颜色映射表 + `_recolor_widget` 递归 | 就地更新、O(1) 查找、避免重建 |
| 用户画像提取 | fire-and-forget 异步 + LLM 提取 + merge 策略 | 异步任务、并发写风险、队列模式 |
| 聊天气泡渲染 | Canvas + 圆角矩形拼接 + `_measure` 动态测量 | 自定义渲染、流式 UI 更新 |
| 宠物数值系统 | mood/hunger/energy 联动 + system_prompt_hint | 数值建模、AI 人格闭环 |
| 便签 ID 生成 | 秒级时间戳（碰撞风险）vs 毫秒时间戳 | ID 策略、碰撞分析 |
| 书签排序 | `_parse_saved_at` 多格式兼容 + epoch 兜底 | 历史数据兼容、防御性降级 |
| 懒加载 | `_news_loaded` / `_weather_loaded` flag | 启动性能、差异化刷新策略 |
| session 持久化 | 从 widget 树逆向提取（反模式）+ 50 条上限 | 数据视图分离、内存管理 |
| 定时衰减 | `win.after` 递归 + `_decay_running` flag | tkinter 定时器、主线程安全 |
