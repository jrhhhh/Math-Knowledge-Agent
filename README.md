# Math Knowledge Agent

一个面向数学学习的 AI Agent 系统。

目标是构建一个能够：

- 保存数学题目与解答
- 建立知识点之间的网络关系
- 自动分析题目涉及的数学概念
- 辅助理解定义、定理与证明过程

的智能数学学习助手。


## Project Status

Current Version: v0.3

已完成：

- [x] FastAPI 后端框架
- [x] SQLite 数据库存储
- [x] SQLAlchemy ORM
- [x] 数学知识点模型（Concept）
- [x] 数学题目模型（Problem）
- [x] 题目创建与查询 API
- [x] AI 数学问答与证明辅助
- [x] 知识图谱关系检索
- [x] AI 按问题生成相关知识图谱
- [x] 候选图谱校验、缓存与幂等入库
- [x] 知识点别名归一化
- [x] 产品化前端展示页


正在开发：

- [x] Problem 与 Concept 知识关联
- [x] 数学知识图谱
- [x] AI 自动提取知识点
- [x] 智能证明分析
- [x] 分步证明分析
- [ ] 个性化学习路径


## Architecture

当前架构：
Math-Agent
Backend
- `GET /ai/health`：查看 DeepSeek 调用成功率、重试次数和最近失败原因
后台重试队列采用单并发和 1.5 秒最小请求间隔，降低触发 DeepSeek 限流的概率；用户当前请求使用高优先级，失败任务重新触发使用普通优先级。
前端 `/ask` 请求支持手动取消，并设置 90 秒客户端超时；后端调用仍有独立超时保护。答案缓存绑定知识库版本，候选图谱保存后会自动失效旧缓存。
缓存管理接口：`GET /ai/cache` 查看命中率，`DELETE /ai/cache` 清空全部答案缓存，`DELETE /ai/cache/{question}` 仅失效指定问题。
AI 错误响应包含 `error_code`：`timeout`、`rate_limit`、`network`、`server_error`、`invalid_response` 或 `unknown`，便于前端展示针对性提示和后续监控。
`/ai/health` 还返回平均响应耗时和平均首 token 耗时，用于定位模型生成瓶颈。
前端知识图谱区域会展示这些指标，并每 30 秒自动刷新。
首 token 超过 3 秒或平均响应超过 20 秒时，监控面板会显示慢请求告警。
每次问答响应都包含 `request_id`，后端耗时日志使用同一 ID，便于端到端排查。
`GET /ai/requests/{request_id}` 可查询本地请求成功记录、耗时和错误信息；`GET /ai/requests` 支持按 `status`、`since`、`until` 筛选最近日志，`GET /ai/requests/export` 可导出 CSV（最多 5000 条），便于分析慢请求趋势。

可选备用模型：设置 `MATH_AGENT_BACKUP_API_KEY`、`MATH_AGENT_BACKUP_BASE_URL` 和可选的 `MATH_AGENT_BACKUP_MODEL`（OpenAI 兼容接口）。主模型失败后会优先切换备用模型，再进入本地兜底；是否配置可通过 `/ai/health` 的 `backup_model_configured` 查看。
管理写操作可设置 `MATH_AGENT_ADMIN_KEY`；配置后，答案复核和审计归档接口必须携带请求头 `X-Admin-Key: <密钥>`，未配置时保持本地开发兼容。
可选安全告警 Webhook：设置 `MATH_AGENT_ALERT_WEBHOOK` 后，管理员携带 Bearer token 调用 `POST /ai/security-alerts/notify` 才会发送当前高危告警；系统不会在后台自动向外部地址发送数据。
日志默认写入 `backend/math_agent.log`，单文件 5 MB、保留 3 个轮转文件；可通过 `MATH_AGENT_LOG_FILE` 和 `MATH_AGENT_LOG_LEVEL` 调整路径与级别。安全事件仍同步写入 SQLite。
本地模板变更可通过 `GET /local-templates/{template_id}/events` 查询审计记录。
匿名样本默认不自动删除，可由管理员调用 `DELETE /local-templates/samples?retention_days=90` 清理过期哈希样本。

启动前后端后，可运行 `./scripts/smoke_test.sh` 做无写入回归检查；也可通过 `API_URL`、`WEB_URL` 环境变量指定服务地址。

GitHub Actions 会在 push 和 pull request 时自动执行编译、后端测试、前端语法检查和 smoke test。
可选监控部署：`docker compose -f docker-compose.monitoring.yml up --build` 会启动后端、Prometheus（9090）和 Grafana（3000）；Prometheus 抓取 `/ai/metrics` 并加载告警规则，Grafana 自动加载 Dashboard，本地直接运行方式不受影响。
数据库备份：执行 `./scripts/backup_db.sh` 使用 SQLite 在线备份生成 `backups/math_agent-时间.db`，默认保留 14 天（可用 `MATH_AGENT_BACKUP_RETENTION_DAYS` 调整）；可用 `./scripts/check_backup.sh backups/xxx.db` 做无写入完整性检查。恢复前请停止后端，执行 `./scripts/restore_db.sh backups/xxx.db`，脚本会先执行 `PRAGMA integrity_check`。可用 cron 每日执行，例如 `0 3 * * * cd /path/to/Math-Agent && ./scripts/backup_db.sh >> /tmp/math-agent-backup.log 2>&1`。
启动迁移会在 `schema_versions` 表记录当前版本，并以增量方式补齐旧数据库字段；不会重建或删除已有数据。
只读数据巡检接口：`GET /maintenance/integrity` 检查孤立题目关联、孤立关系端点、重复关系和重复概念名称，不会自动修改数据。
修复前预览接口：`GET /maintenance/integrity/repair-preview` 列出可疑记录和建议动作，仍然只读。
管理员先调用 `POST /maintenance/integrity/repair/prepare` 获取 10 分钟一次性确认令牌，再调用 `POST /maintenance/integrity/repair` 并携带令牌和同一组记录 ID；接口会先生成 `math_agent-before-repair-时间.db` 备份，再执行精确删除。
可用 `./scripts/rehearse_restore.sh backups/xxx.db` 做恢复演练；它只恢复到临时目录并检查关键表，不会覆盖生产数据库。
运维控制台也提供管理员保护的 `POST /maintenance/backup` 手动备份和 `GET /maintenance/backups` 备份列表接口；网页不会直接执行恢复。
Prometheus 指标还包含备份成功/失败次数及最后备份时间戳，可据此配置备份失败或长期未备份告警。
CI 还会使用无头 Chromium 检查公式测试页的 MathJax 实际渲染结果。
- `POST /ai/retry-queue`：将失败的相关图谱请求加入后台重试队列
- `GET /ai/retry-queue/{job_id}`：查询后台重试任务状态和结果
- `GET /ai/retry-queue`：查看最近后台重试任务
- `POST /ai/retry-queue/{job_id}/retry`：重新触发已结束的失败或成功任务
- `POST /ai/retry-queue/{job_id}/cancel`：取消尚未结束的后台重试任务
重试任务持久化在 SQLite；服务重启时会自动恢复 queued、running 和 retrying 状态的任务。
│
├── FastAPI
│
├── SQLAlchemy
│
├── SQLite
│
├── Models
│   ├── Concept
│   └── Problem
│
└── API
    ├── Concepts
    └── Problems


未来目标：
             LLM
              |
              |
    Problem ---- Knowledge Graph
              |
              |
         Concepts
              |
              |
      Learning Assistant


## Features

### Problem Management

支持保存：

- 题目标题
- 题目内容
- 解答过程
- 难度等级
- 创建时间


### Knowledge Management

当前支持：

- 定义、定理、性质和方法分类
- prerequisite、uses、supports、property_of 等关系
- 关系方向与冲突校验
- 知识网络可视化

### Frontend

`frontend/` 是一个无需构建工具的产品展示界面，包含：

- 数学问题输入与 AI 回答
- 相关知识点展示
- 知识图谱可视化
- 分步证明审查与错误定位
- MathJax 数学公式排版
- 响应式布局与移动端适配

### AI API

- `POST /ai/ask`：数学问答、知识点检索和历史题推荐
- `POST /ai/proof-analyze`：分步检查证明、缺失条件和逻辑错误
- `POST /ai/related-graph`：由 AI 根据问题生成候选知识图谱；相同问题 24 小时内复用缓存
- `GET /ai/graph-candidates`：分页查看候选图谱，可按状态筛选
- `GET /ai/graph-candidates/stats`：查看各审核状态的候选数量
- `POST /ai/graph-candidates/batch-validate`：批量执行候选图谱校验，单条失败不影响其他记录
- `POST /ai/graph-candidates/batch-save-preview`：预览批量保存将新增、替换和跳过的内容
- `POST /ai/graph-candidates/batch-save`：批量幂等保存已通过校验的候选图谱
- `GET /ai/graph-candidates/{candidate_id}`：查看候选图谱及校验状态
- `GET /ai/graph-candidates/{candidate_id}/events`：查看候选图谱生成、编辑、校验和保存时间线
- `PUT /ai/graph-candidates/{candidate_id}`：审核者修改候选图谱；修改后自动回到 `pending`
- `POST /ai/graph-candidates/{candidate_id}/validate`：执行格式和数学语义校验
- `POST /ai/graph-candidates/{candidate_id}/save`：将通过校验的概念和关系幂等写入知识库
- `GET /concepts/graph`：获取知识图谱节点和关系
- `POST /concepts/{concept_id}/aliases`：为已有知识点添加别名

`/ai/ask` 已采用本地知识点优先检索，并使用知识点综合分数排序历史题，减少不必要的 LLM 调用。

相关图谱的典型流程：

```text
问题 → AI 生成候选图谱 → 代码校验 → AI 语义校验 → 显式保存 → 知识库复用
```

候选图谱中的新概念在保存前只作为临时节点展示；保存时会按标准名称和别名去重，并按关系优先级处理冲突。已有数据库不会被首次启动或生成操作删除。

启动前端展示页：

```bash
cd frontend
python3 -m http.server 5500
```

浏览器打开：`http://127.0.0.1:5500`

同时启动后端：

```bash
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload
```


## Tech Stack

Backend:

- Python
- FastAPI
- SQLAlchemy
- SQLite


Development:

- Git
- GitHub
- VS Code


## Installation

Clone repository:

```bash
git clone https://github.com/jrhhhh/Math-Knowledge-Agent.git
进入 backend:
```bash
cd Math-Knowledge-Agent/backend
python3 -m venv .venv
./.venv/bin/pip install fastapi uvicorn sqlalchemy openai python-dotenv
./.venv/bin/python -m uvicorn app.main:app --reload
```
打开：
http://127.0.0.1:8000/docs

前端另开一个终端启动：

```bash
cd frontend
python3 -m http.server 5500
```

访问：`http://127.0.0.1:5500/index.html`

## Roadmap
Phase 1: Backend Foundation
- Database
- API
- Data Models
Phase 2: Knowledge Graph
- Concept relationships
- Problem knowledge mapping
Phase 3: AI Agent
- Automatic problem understanding
- Knowledge extraction
- Proof explanation
- Learning recommendation
Author
jrhhhh

---
