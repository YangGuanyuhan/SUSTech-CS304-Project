# Web Search 功能

## 概述

Web Search 功能允许 Agent 通过 Brave Search API 搜索互联网，获取最新的信息、新闻、价格、天气等实时数据。

## 设计理念

### 条件性激活

本功能采用**条件性激活**设计：

- **无 API key**：功能完全保持原样，`web_search` 工具不会注册到 Agent
- **有 API key**：自动启用搜索功能，无需手动切换

这种设计确保了：
1. 向后兼容：未配置 API key 的用户不受影响
2. 安全性：API key 存储在 `.env` 文件中，不会暴露到前端
3. 灵活性：用户可以随时启用或禁用功能

### 架构集成

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent (PydanticAI)                      │
├─────────────────────────────────────────────────────────────┤
│  条件性注册: 只有配置了 BRAVE_API_KEY 才注册 web_search 工具  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              AgentToolService (工具执行层)                    │
├─────────────────────────────────────────────────────────────┤
│  get_tool_definitions(): 根据配置动态添加工具定义            │
│  execute(): 路由到 _web_search() 方法                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              SearchService (搜索服务层)                      │
├─────────────────────────────────────────────────────────────┤
│  search_web(): 调用 Brave Search API                        │
│  支持参数: query, max_results, country, search_lang, freshness│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Brave Search API                          │
└─────────────────────────────────────────────────────────────┘
```

## 使用说明

### 1. 获取 API Key

1. 访问 [Brave Search API](https://brave.com/search/api/)
2. 注册账号并选择套餐（免费套餐：2,000 次/月）
3. 在 Dashboard 中创建 API Key
4. 复制 `BSA-xxxxxxxx` 格式的 Key

### 2. 配置环境变量

在项目根目录的 `.env` 文件中添加：

```env
BRAVE_API_KEY=BSA-xxxxxxxx
```

### 3. 重启后端服务

```bash
uv run uvicorn backend.main:app --reload
```

### 4. 使用搜索功能

在聊天中直接询问需要搜索的问题：

- "今天的新闻有哪些？"
- "比特币现在价格是多少？"
- "Python 最新版本是什么？"
- "深圳明天天气怎么样？"
- "2024 年诺贝尔物理学奖得主是谁？"

Agent 会自动判断是否需要搜索，并调用 `web_search` 工具获取最新信息。

## 功能特性

### 搜索参数

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| `query` | 搜索关键词 | 必填 | 任意字符串 |
| `max_results` | 返回结果数量 | 5 | 1-10 |
| `country` | 地区偏好 | CN | CN, US, JP, etc. |
| `search_lang` | 搜索语言 | zh-hans | zh-hans, en, etc. |
| `freshness` | 时效性过滤 | 无 | pd(今天), pw(本周), pm(本月), py(今年) |

### 返回结果格式

```json
{
  "results": [
    {
      "title": "结果标题",
      "url": "https://example.com",
      "snippet": "结果摘要...",
      "published_date": "2024-01-15T10:30:00Z"
    }
  ],
  "query": "搜索关键词",
  "count": 5
}
```

### 错误处理

| 场景 | 处理方式 |
|------|----------|
| 无 API key | 工具不注册，Agent 无法调用 |
| API key 无效 | 返回错误信息，提示检查配置 |
| 网络超时 | 返回友好错误信息 |
| 搜索无结果 | 返回空结果列表 |
| API 限流 | 返回错误信息，提示稍后重试 |

## 搜索触发逻辑

### 核心原则

**不是每次提问都调用搜索**。Agent 会智能判断何时需要搜索：

1. **用户明确要求搜索时**
   - "搜索一下今天的新闻"
   - "帮我查一下比特币价格"
   - "look up latest Python version"

2. **本地工具无法回答时**
   - 先尝试 `rag_search` / `rag_answer`（本地知识库）
   - 再尝试 `memory_search`（对话记忆）
   - 如果都没有结果，才使用 `web_search`

3. **需要实时信息时**
   - 今天的新闻、当前价格、实时天气
   - 最近发生的事件（几个月内）

### 搜索优先级

```
用户提问
    │
    ▼
┌─────────────────┐
│ 明确要求搜索？   │──是──▶ web_search
└────────┬────────┘
         │否
         ▼
┌─────────────────┐
│ 需要实时信息？   │──是──▶ web_search
└────────┬────────┘
         │否
         ▼
┌─────────────────┐
│ 本地知识库有答案？│──是──▶ rag_search/rag_answer
└────────┬────────┘
         │否
         ▼
┌─────────────────┐
│ 记忆中有答案？   │──是──▶ memory_search
└────────┬────────┘
         │否
         ▼
    使用训练知识回答
```

### 适合搜索的场景

**用户明确要求**
- "搜索..."
- "查找..."
- "look up..."
- "search for..."

**实时信息**
- 新闻、时事
- 股票、加密货币价格
- 天气预报
- 体育赛事结果

**近期事件**
- 最新发布的产品
- 最近的会议、活动
- 最新的研究论文

### 不适合搜索的场景

**常识性问题**
- "Python 是什么？"
- "什么是机器学习？"

**本地信息**
- 本地文件内容
- 已上传的文档
- 个人记忆、笔记

**不需要最新信息的问题**
- 历史事件（已定论的）
- 数学公式
- 编程语法

## 技术细节

### 配置检查逻辑

```python
# 在 get_tool_definitions() 和 _build_agent() 中
from backend.config import get_settings
settings = get_settings()

if settings.brave_api_key and settings.brave_api_key.strip():
    # 注册 web_search 工具
    # 添加搜索相关系统提示
    # 启用工具学习
```

### 搜索服务实现

```python
class SearchService:
    async def search_web(
        self,
        query: str,
        max_results: int = 5,
        country: str = "CN",
        search_lang: str = "zh-hans",
        freshness: str | None = None,
    ) -> list[SearchResult]:
        # 调用 Brave Search API
        # 返回格式化结果
```

### 工具定义

```python
{
    "name": "web_search",
    "description": "Search the internet using Brave Search...",
    "parameters": {
        "query": {"type": "string", "required": True},
        "max_results": {"type": "integer", "default": 5},
        "country": {"type": "string", "default": "CN"},
        "search_lang": {"type": "string", "default": "zh-hans"},
        "freshness": {"type": "string", "enum": ["pd", "pw", "pm", "py"]}
    }
}
```

## 速率限制与配额

### Brave Search 免费套餐

- **每月查询次数**: 2,000 次
- **每秒查询数**: 1 QPS
- **结果数量**: 最多 20 条/次

### 优化建议

1. **合理设置 `max_results`**: 默认 5 条通常足够，避免浪费配额
2. **使用 `freshness` 过滤**: 如果只需要近期信息，使用时效性过滤
3. **缓存结果**: 对于相同查询，可以考虑缓存结果（未来优化）

## 故障排查

### 问题：Agent 不调用搜索工具

**可能原因**:
1. `.env` 中未配置 `BRAVE_API_KEY`
2. API key 格式错误（应为 `BSA-xxxxxxxx`）
3. 后端未重启

**解决方法**:
1. 检查 `.env` 文件
2. 确认 API key 格式正确
3. 重启后端服务

### 问题：搜索返回错误

**可能原因**:
1. API key 无效或过期
2. 网络连接问题
3. 达到速率限制

**解决方法**:
1. 在 Brave Search Dashboard 检查 API key 状态
2. 检查网络连接
3. 等待一段时间后重试

### 问题：搜索结果不准确

**可能原因**:
1. 搜索关键词不够精确
2. 搜索语言/地区设置不合适

**解决方法**:
1. 使用更精确的关键词
2. 尝试设置不同的 `country` 和 `search_lang` 参数

## 未来优化方向

1. **结果缓存**: 缓存相同查询的结果，减少 API 调用
2. **多搜索引擎支持**: 支持 Tavily、Google 等其他搜索引擎
3. **搜索历史**: 记录搜索历史，优化搜索体验
4. **结果摘要**: 使用 LLM 对搜索结果进行摘要
5. **图片搜索**: 支持图片搜索功能

## 相关文件

- `backend/config.py` - 配置定义
- `backend/services/search_service.py` - 搜索服务实现
- `backend/services/agent_tool_service.py` - 工具定义和执行
- `backend/agent/pydantic_runtime.py` - PydanticAI 工具注册
- `tests/test_web_search.py` - 单元测试
