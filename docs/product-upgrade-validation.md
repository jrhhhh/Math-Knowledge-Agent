# 产品升级交付与验证入口

2026-10-10。本轮九项功能已按顺序完成接口/数据检查与真实 Chrome 操作。逐项操作和证据见 [product-upgrade-plan.md](product-upgrade-plan.md)。

## 当前运行

- 网站：http://127.0.0.1:5500/index.html
- API：http://127.0.0.1:8000
- 当前已切回 `backend/math_agent.db`，验收作答/笔记/教材保留在独立 `evaluation/runs/product-upgrade/acceptance.db`。
- 真实数据库迁移前备份：`evaluation/runs/product-upgrade/user-before-upgrade-20261010.db`，SQLite 完整性检查通过。
- 35 张原业务表按迁移前列逐行摘要比较，原数据完全一致；schema_versions 按预期增加迁移版本。新增表及作答列正常。
- 当前进程保留 `MATH_AGENT_DISABLE_RETRY_WORKER=1`。原库有 169 个历史 running 重试任务，本轮不自动重放；这仅影响后台重试，正常同步对话/计算/教材/练习可用。代码的默认启动行为未修改。

## 验证命令

在项目根目录运行前端数值与语法检查：

```sh
node frontend/tests/math-lab-core.test.cjs
node --check frontend/math-lab.js
node --check frontend/learning-metrics.js
git diff --check
```

在 backend 目录运行全部后端测试，必须指定独立数据库：

```sh
MATH_AGENT_DB_PATH=/Users/jiaruiheng/Desktop/Math-Agent/evaluation/runs/product-upgrade/tests.db MATH_AGENT_DISABLE_RETRY_WORKER=1 .venv/bin/python -m unittest discover -s tests -q
```

本轮最终结果：181 项后端测试通过；数学实验数值边界检查通过；所有前端 JavaScript 文件语法检查通过。原始日志：`evaluation/runs/product-upgrade/final-tests.log`。

本地服务再次启动时，在 backend 目录执行：

```sh
MATH_AGENT_DB_PATH=/Users/jiaruiheng/Desktop/Math-Agent/backend/math_agent.db MATH_AGENT_DISABLE_RETRY_WORKER=1 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端在 frontend 目录执行：

```sh
python3 -m http.server 5500 --bind 127.0.0.1
```

## 完成证据与边界

| 计划项 | 浏览器操作证据 | 数据/自动检查证据 |
| --- | --- | --- |
| 1 工作台 | 讲解/提示/检查、草稿延续、管理分区、320/390 窄屏 | tutoring modes 与会话测试 |
| 2 依据展示 | 真实工具与教材来源弹窗、模型审查标签 | answer links/verification 范围测试 |
| 3 作答反馈 | 错答、首错人工反馈、修订重交 | problem attempt 关系与状态测试 |
| 4 间隔复习 | 重测隐藏历史、后续错误重置当前状态 | 1/3/7/14/30 天与稳定状态边界测试 |
| 5 图谱路径 | 前置顺序、实际题目带入、推荐理由 | learning path actions 测试 |
| 6 笔记 | 保存/编辑/收藏/归档/恢复/下载 | immutable origin、导出与对话原题测试 |
| 7 教材 | PDF 真实上传、双栏校对、原稿翻页、选段真实回答 | PDF/空页/审核/修订/原稿读取测试 |
| 8 实验 | h 收敛/不可导点、反向积分、旋转/奇异矩阵、参数复位与带入 | 数值边界 JS 测试；线性图使用等比例坐标 |
| 9 统计 | 三个范围、原始编号、刷新每日去重、实际 JSON 导出 | 同一分母、24 小时、反馈先后、最新评分、HTTP 查询测试 |

真实数据库浏览器复核：历史验收新增数据不出现；原有 1 份待审核作答对应审核等待“暂无样本”、已审核与延迟成功均 0；访问从当前真实打开日开始采集。320px 页面宽度无横向溢出，7 个入口均可见。

DeepSeek 官方余额接口本轮最后返回 `is_available=true`。没有宣称长期监控或已观察到长期学习提升。扫描 PDF 没有文字层时仍需补录；模型审查仍不等同数学证明。

截图位于 `output/playwright/`，编号 step1 至 step9 对应逐项验收。历史中间失败/权限截图仅记录过程，最终状态以完整验收章节与 final 截图为准。
