# 数据库重构总结

## 1. 背景

这个仓库是一个软件工程小组项目，主题是学生生产力 Agent。  
原来的数据库层虽然能跑，但是结构上有几个明显问题：

- 大量同步 SQLAlchemy 调用被包在 `async def` 的 CRUD 函数里
- 多个字段用手工 JSON 字符串存储，service 层反复 `json.dumps` / `json.loads`
- quiz 相关表的关系设计比较弱
- 数据层不利于继续扩展文档里提到的后续需求
- 没有专门的数据库可视化入口，不方便演示和验收

这次重构是在下面这个分支完成的：

```bash
feat-db-refactor-foundation
```

起始分支是：

```bash
dev-pydanticAI
```

## 2. 重构前阅读过的内容

在正式改代码之前，先通读并检查了这些内容：

- `README.md`
- `TECHNICAL_DESIGN.md`
- `proposal-26s-8.md`
- `backend/db/` 下现有数据库代码
- `backend/services/` 下相关服务层代码
- `tests/` 下现有测试

从文档里提炼出的、和数据库未来演进最相关的要求主要有：

- 会话存储应从浏览器本地迁移到后端数据库
- memory 检索后续应该支持 embedding 或更强的召回方式
- 邮件流程后续应该支持 approval history
- 架构应保持对 PostgreSQL 迁移的兼容性
- 模块化要清晰，方便后续继续开发和替换

## 3. 原始数据库层存在的问题

### 3.1 持久化层问题

- 多个本应是结构化数据的字段被直接存成字符串，例如：
  - memory 的 value
  - memory 的 tags
  - Blackboard cache 的 payload
  - task history 的 tools_used
  - quiz question 的 options

这会导致 service 层反复做 JSON 编解码，逻辑分散而且容易出错。

### 3.2 表结构问题

- quiz 相关表之间关系不够明确
- 缺少外键和级联删除
- 一些关键的唯一性约束和索引没有落到模型层

### 3.3 代码组织问题

- `backend/db/crud.py` 已经变成一个非常杂的大文件
- service 层知道太多底层存储细节
- 有些测试 mock 的方法已经过时，表面上在测 fallback，实际上并没有真测到

### 3.4 展示和调试问题

- 没有一个可直接查看数据库状态的页面或接口
- 做课程汇报时，很难把“数据库改好了”这件事直观展示出来

## 4. 这次具体做了什么

### 4.1 升级 ORM 模型

文件：

- `backend/db/models.py`

主要改动：

- 增加了更合理的索引
- 增加了唯一约束
- 为 quiz 相关表补上了外键
- 增加了级联删除
- 把多个原先手工字符串化的 JSON 字段改成 typed JSON 列
- 把 quiz answer 里的 `is_correct` 从字符串改成了可空布尔值

具体例子：

- `MemoryRecord.value` 代替了原来的 `value_json`
- `MemoryRecord.tags` 代替了原来的 `tags_json`
- `TaskHistoryRecord.tools_used` 代替了原来的 `tools_used_json`
- `QuizQuestionRecord.options` 代替了原来的 `options_json`

### 4.2 新增可复用 JSON 列类型

新文件：

- `backend/db/types.py`

新增了一个自定义 SQLAlchemy 类型：

- `JSONText`

它的作用是：

- 让 Python 结构化对象以统一方式存进数据库文本列
- 避免每个 service 手工写一遍序列化逻辑
- 保持 SQLite 兼容，同时对后续迁移更友好

### 4.3 引入 repository 层

新文件：

- `backend/db/repositories.py`

新增的 repository 包括：

- `MemoryRepository`
- `EmailDraftRepository`
- `BlackboardCacheRepository`
- `TaskHistoryRepository`
- `UserPreferenceRepository`
- `QuizRepository`
- `DatabaseAnalyticsRepository`

这样做的目的：

- 把 SQL 访问逻辑收回到数据库层
- 降低 service 层对 SQLAlchemy 细节的直接依赖
- 给以后继续重构留出更清晰的边界

### 4.4 保留了兼容层

更新文件：

- `backend/db/crud.py`

没有粗暴删掉原有调用面，而是让 `crud.py` 变成 repository 的兼容包装层。  
这样可以在不大面积破坏调用方的前提下，把内部结构先整理好。

### 4.5 清理 service 层

更新文件：

- `backend/services/memory_service.py`
- `backend/services/email_service.py`
- `backend/services/quiz_service.py`
- `backend/services/settings_service.py`
- `backend/services/task_service.py`
- `backend/services/blackboard_service.py`

主要改进：

- 去掉了很多手工 JSON 解析
- service 层开始通过 repository 访问数据
- 领域对象转换路径更直接
- quiz history 的错题判断改成真正依赖布尔值，而不是字符串 `"false"`

### 4.6 新增数据库概览 API

新文件：

- `backend/services/database_insights_service.py`

新模型文件：

- `backend/models/database.py`

更新接口文件：

- `backend/api/routes.py`

新增接口：

```http
GET /api/database/overview
```

这个接口会返回：

- 各表数量统计
- memory 分类分布
- 最近 task history
- session 活跃度
- 最近一次 quiz attempt 概览
- schema readiness 状态

### 4.7 新增前端数据库可视化面板

更新文件：

- `frontend/src/App.vue`
- `frontend/src/api/client.js`

新增文件：

- `frontend/src/components/DatabaseOverviewPanel.vue`

这个改动带来了：

- 首页新增 `Database View` 按钮
- 点击后可以直接看数据库概览
- 这对课程汇报、调试和验收都更直观

### 4.8 更新并补充测试

更新文件：

- `tests/test_quiz_service.py`

新增文件：

- `tests/test_database_insights.py`

做了这些事：

- 修正了 quiz 测试里过期的 mock 位置
- 为新的数据库概览 service 加了测试
- 验证数据库重构后的主要路径仍然可用

## 5. 为什么这次重构更好

### 更易维护

- 数据序列化逻辑被集中处理
- repository 把 SQL 细节从 service 层隔离出来
- 表关系和约束比原来更明确

### 更易扩展

现在的结构更适合继续往下做：

- 后端 conversation storage
- memory embedding 检索
- email approval history
- 更丰富的数据统计与可视化

### 更适合展示

这次不只是“内部写法更规范”，还补了一个数据库总览面板，方便在演示时直接展示数据库层已经做了哪些增强。

## 6. 这次重构中明确提出的后续方向

下面这些是基于当前文档和现状，下一步最值得做的数据库方向。

### 6.1 增加 conversation 相关表

建议的未来表：

- `conversations`
- `conversation_messages`

原因：

- 设计文档里已经明确提出要把前端本地会话存储迁移到后端
- 当前 `task_history` 能凑合用，但不适合作为长期唯一会话真相源

### 6.2 升级 memory 检索

建议的未来扩展：

- embedding 字段或 embedding 辅助表
- 混合检索
- 排名相关元数据

原因：

- 设计文档里明确写了要从 keyword matching 升级到更强的 memory retrieval

### 6.3 增加邮件审批历史

建议的未来扩展：

- 邮件审批记录表
- 记录审批人、时间、结果

原因：

- 提案和设计文档都强调了邮件必须 human-in-the-loop

### 6.4 引入 migration 工具

建议未来加入：

- Alembic 或同类迁移机制

原因：

- 现在 schema 已经比原来复杂了
- 再继续演进时，不应该长期只依赖 `create_all`

### 6.5 增强数据库运维可视化

后续可继续扩展：

- Blackboard cache 新鲜度统计
- 每个 session 的工具使用统计
- memory 数量增长趋势
- quiz 成绩变化趋势图

## 7. 新增和修改的文件

### 新增文件

- `backend/db/types.py`
- `backend/db/repositories.py`
- `backend/models/database.py`
- `backend/services/database_insights_service.py`
- `frontend/src/components/DatabaseOverviewPanel.vue`
- `tests/test_database_insights.py`
- `DATABASE_REFACTOR_SUMMARY.md`
- `DATABASE_REFACTOR_SUMMARY_ZH.md`

### 修改文件

- `backend/api/routes.py`
- `backend/db/crud.py`
- `backend/db/models.py`
- `backend/services/blackboard_service.py`
- `backend/services/email_service.py`
- `backend/services/memory_service.py`
- `backend/services/quiz_service.py`
- `backend/services/settings_service.py`
- `backend/services/task_service.py`
- `frontend/src/App.vue`
- `frontend/src/api/client.js`
- `tests/test_quiz_service.py`

## 8. 你怎么查看这些改动

### 8.1 先确认当前分支

```bash
git branch --show-current
```

预期输出：

```bash
feat-db-refactor-foundation
```

### 8.2 查看当前改动文件

```bash
git status
```

### 8.3 查看全部差异

```bash
git diff
```

### 8.4 只看数据库模型改动

```bash
git diff -- backend/db/models.py
```

### 8.5 只看 repository 层

```bash
git diff -- backend/db/repositories.py
```

### 8.6 只看数据库概览 API

```bash
git diff -- backend/api/routes.py backend/services/database_insights_service.py backend/models/database.py
```

### 8.7 只看前端数据库面板

```bash
git diff -- frontend/src/App.vue frontend/src/api/client.js frontend/src/components/DatabaseOverviewPanel.vue
```

## 9. 你怎么运行项目并查看这次数据库改造

### 9.1 启动后端

在仓库根目录执行：

```bash
uv run uvicorn backend.main:app --reload
```

### 9.2 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

### 9.3 打开页面

打开 Vite 提示的前端地址，通常是：

```text
http://127.0.0.1:5173
```

### 9.4 查看数据库可视化

在主页上：

1. 启动前端
2. 保证后端正在运行
3. 点击 `Database View`
4. 查看：
   - 各表数量
   - memory 分类
   - 最近 task history
   - session 活跃度
   - 最近 quiz attempt
   - schema readiness

### 9.5 如果面板里数据很少

可以先在系统里制造一些数据：

- 用聊天窗口发起对话
- 使用 memory 相关功能
- 创建 quiz
- 提交 quiz attempt
- 在 settings 里保存 LLM profile

然后再打开 `Database View`。

## 10. 你怎么直接查询新的数据库概览接口

启动后端后，可以直接请求这个接口：

### 浏览器直接打开

```text
http://127.0.0.1:8000/api/database/overview
```

### PowerShell

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/database/overview
```

### curl

```bash
curl http://127.0.0.1:8000/api/database/overview
```

## 11. 你怎么跑相关测试

建议使用下面这个命令：

```bash
uv run pytest tests\test_memory.py tests\test_quiz_service.py tests\test_settings_service.py tests\test_database_insights.py
```

这组测试已经验证通过。

## 12. 额外说明

### 仓库里原本存在的无关改动

在这次数据库重构开始时，仓库里就已经有一些与本次工作无关的本地改动，比如：

- `frontend/package-lock.json`
- `package-lock.json`

这些不是本次数据库重构本身的一部分。

### 当前 schema 演进方式的限制

现在项目仍然通过 `Base.metadata.create_all(...)` 初始化表结构。  
对课程项目当前阶段来说可以接受，但如果后续数据库继续扩展，建议尽快补 migration 机制。

## 13. 简短总结

这次重构把原本比较草率、混杂的数据层，整理成了一套更像样的基础：

- 更明确的关系建模
- 更安全的 typed JSON 存储
- 更清晰的 repository 组织方式
- 更干净的 service 接入
- 一个可直接展示的数据库总览面板
- 对新功能的测试覆盖

同时，这次改动也为文档里已经写到的几个未来方向打下了更合适的基础，包括：

- conversation backend 存储
- memory embedding 检索
- email approval history
- 更完整的数据库迁移和统计能力
