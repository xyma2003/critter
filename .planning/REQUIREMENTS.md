# Requirements: Critter

**Defined:** 2026-04-16
**Core Value:** 宠物始终在桌面陪伴——悬浮窗随时可见、可交互，让用户感受到有个小伙伴在场。

## v1 Requirements

### 新闻收藏

- [x] **NEWS-01**: 用户可以收藏单条新闻（标题+链接+来源），数据持久化到本地 JSON
- [x] **NEWS-02**: 用户可以将新闻标记为「稍后再看」，与收藏分开存储
- [x] **NEWS-03**: 用户可以在新闻 Tab 查看收藏列表和稍后再看列表（独立视图）
- [x] **NEWS-04**: 用户可以从收藏/稍后再看列表中删除条目
- [x] **NEWS-05**: 数据访问通过 StorageRepository 类封装，底层 JSON 可替换为数据库

### 天气

- [x] **WTHR-01**: 用户可以在天气 Tab 查看当前城市的实时天气（温度、天气状况、体感温度）
- [x] **WTHR-02**: 用户可以添加任意城市到天气列表（支持中英文城市名）
- [ ] **WTHR-03**: 用户可以删除已添加的城市
- [x] **WTHR-04**: 天气数据通过 wttr.in 免费 API 获取，异步加载不阻塞 UI
- [x] **WTHR-05**: 用户可以查看未来3天天气预报
- [x] **WTHR-06**: 天气 Tab 有手动刷新按钮，数据缓存15分钟避免频繁请求

### 心情系统

- [ ] **MOOD-01**: 宠物有心情值（0-100），持久化到 settings.json
- [ ] **MOOD-02**: 心情值随时间自动缓慢衰减（每小时衰减约5点，下限20）
- [ ] **MOOD-03**: 用户与宠物对话后心情值上升（每次对话 +5，上限100）
- [ ] **MOOD-04**: 宠物 Tab 有「喂食」「玩耍」「抚摸」互动按钮，每次互动提升心情（+10~+15）
- [ ] **MOOD-05**: 心情值影响主页欢迎语（高兴/普通/无聊三档文案）
- [ ] **MOOD-06**: 心情值影响悬浮窗 emoji（高兴/普通/无聊对应不同表情）
- [ ] **MOOD-07**: 宠物 Tab 显示心情进度条和当前心情档位文字

### 宠物自定义图片

- [ ] **PET-01**: 用户可以在宠物 Tab 或设置 Tab 上传本地图片作为宠物头像
- [ ] **PET-02**: 上传的图片自动裁剪为圆形，存储到本地（复制到应用目录）
- [ ] **PET-03**: 悬浮窗显示自定义图片替代默认 emoji（保持原有动画效果）
- [ ] **PET-04**: 主页对话气泡左侧头像显示自定义图片
- [ ] **PET-05**: 宠物 Tab 展示区显示自定义图片（大尺寸）
- [ ] **PET-06**: 用户可以恢复默认 emoji，删除自定义图片

## v2 Requirements

### 成就系统

- **ACHV-01**: 累计对话次数达到里程碑时宠物有特殊反应
- **ACHV-02**: 记录第一次对话、最长连续使用天数等纪念日

### 便签增强

- **NOTE-01**: 便签支持 checkbox，可作为待办清单使用
- **NOTE-02**: 便签支持标签分类

### 通知增强

- **NOTF-01**: 新闻定时刷新后通过 macOS 通知推送摘要
- **NOTF-02**: 心情过低时宠物主动发起对话提醒

## Out of Scope

| Feature | Reason |
|---------|--------|
| 云端同步 / 账号系统 | 当前定位本地单机，未来里程碑再考虑 |
| Windows / Linux 支持 | 依赖 macOS 专属 API |
| 移动端 | 桌面专属场景 |
| 视频/GIF 宠物动画 | tkinter 渲染能力有限，复杂度高 |
| 多宠物切换 | 当前聚焦单宠物体验 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| NEWS-01 | — | Complete |
| NEWS-02 | — | Complete |
| NEWS-03 | — | Complete |
| NEWS-04 | — | Complete |
| NEWS-05 | — | Complete |
| WTHR-01 | — | Complete |
| WTHR-02 | — | Complete |
| WTHR-03 | — | Pending |
| WTHR-04 | — | Complete |
| WTHR-05 | — | Complete |
| WTHR-06 | — | Complete |
| MOOD-01 | — | Pending |
| MOOD-02 | — | Pending |
| MOOD-03 | — | Pending |
| MOOD-04 | — | Pending |
| MOOD-05 | — | Pending |
| MOOD-06 | — | Pending |
| MOOD-07 | — | Pending |
| PET-01 | — | Pending |
| PET-02 | — | Pending |
| PET-03 | — | Pending |
| PET-04 | — | Pending |
| PET-05 | — | Pending |
| PET-06 | — | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 24 ⚠️

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-16 after initial definition*
