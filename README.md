# Math Knowledge Agent

一个面向数学学习的 AI Agent 系统。

目标是构建一个能够：

- 保存数学题目与解答
- 建立知识点之间的网络关系
- 自动分析题目涉及的数学概念
- 辅助理解定义、定理与证明过程

的智能数学学习助手。


## Project Status

Current Version: v0.2

已完成：

- [x] FastAPI 后端框架
- [x] SQLite 数据库存储
- [x] SQLAlchemy ORM
- [x] 数学知识点模型（Concept）
- [x] 数学题目模型（Problem）
- [x] 题目创建与查询 API
- [x] AI 数学问答与证明辅助
- [x] 知识图谱关系检索
- [x] 产品化前端展示页


正在开发：

- [ ] Problem 与 Concept 知识关联
- [x] 数学知识图谱
- [x] AI 自动提取知识点
- [x] 智能证明分析
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
- 响应式布局与移动端适配

启动前端展示页：

```bash
cd frontend
python3 -m http.server 5500
```

浏览器打开：`http://127.0.0.1:5500`

同时启动后端：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
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
cd backend
创建虚拟环境:
python3 -m venv .venv
安装依赖:
pip install fastapi uvicorn sqlalchemy openai python-dotenv
启动:
uvicorn app.main:app --reload
```
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
