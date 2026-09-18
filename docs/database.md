# Database Design


## 数据实体


## Concept

数学概念。

例如：

- 完备性
- 紧致性
- 连续性


字段：

- id
- name
- description
- field


## Definition

数学定义。


字段：

- id
- title
- content
- concept_id


## Theorem

数学定理。


字段：

- id
- title
- statement
- proof


## Problem

数学题目。


字段：

- id
- question
- difficulty
- source


## Solution

用户解答。


字段：

- id
- problem_id
- content
- feedback


## Mistake

用户错误。


字段：

- id
- description
- category
- frequency


## Learning Event

学习记录。


字段：

- id
- date
- object
- progress
# Database storage

Math Agent persists its SQLite data in `backend/math_agent.db` by default.
The location is independent of the directory from which Uvicorn is started,
so task history, completed answers, graph candidates, feedback, and local
templates continue to use one database file.

To store the data elsewhere, set the same environment variable used by the
backup scripts before starting the application:

```bash
export MATH_AGENT_DB_PATH="/absolute/path/to/math-agent.db"
./.venv/bin/python -m uvicorn app.main:app --reload
```

The parent directory is created automatically. Backups and restore rehearsal
commands read `MATH_AGENT_DB_PATH` as well, ensuring they target this same
file.
