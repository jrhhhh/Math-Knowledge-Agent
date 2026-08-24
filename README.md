# Math Knowledge Agent

一个面向数学学习的 AI Agent 系统。

目标是构建一个能够：

- 保存数学题目与解答
- 建立知识点之间的网络关系
- 自动分析题目涉及的数学概念
- 辅助理解定义、定理与证明过程

的智能数学学习助手。


## Project Status

Current Version: v0.1

已完成：

- [x] FastAPI 后端框架
- [x] SQLite 数据库存储
- [x] SQLAlchemy ORM
- [x] 数学知识点模型（Concept）
- [x] 数学题目模型（Problem）
- [x] 题目创建与查询 API


正在开发：

- [ ] Problem 与 Concept 知识关联
- [ ] 数学知识图谱
- [ ] AI 自动提取知识点
- [ ] 智能证明分析
- [ ] 个性化学习路径


## Architecture

当前架构：
Math-Agent
Backend
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

未来支持：

- 定义管理
- 定理关联
- 证明依赖
- 知识网络


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
cd backend
创建虚拟环境:
python3 -m venv .venv
安装依赖:
pip install fastapi uvicorn sqlalchemy
启动:
uvicorn app.main:app --reload
打开：
http://127.0.0.1:8000/docs
Roadmap
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

## 3. 保存

VS Code：