# System Architecture


## 1. 总体架构


User

↓

Frontend

↓

Backend API

↓

AI Agent Layer

↓

Database Layer

↓

External AI Service



## 2. Frontend

技术：

- Next.js
- React
- TypeScript


负责：

- 用户界面
- AI聊天
- 知识图谱展示
- 题目管理


## 3. Backend

技术：

- Python
- FastAPI


负责：

- API接口
- 用户请求处理
- Agent调用
- 数据处理


## 4. AI Agent Layer


### Teacher Agent

负责：

- 数学解释
- 概念教学


### Knowledge Agent

负责：

- 提取知识点
- 建立关系


### Proof Agent

负责：

- 分析证明
- 查找漏洞


### Review Agent

负责：

- 学习总结
- 错误分析


## 5. Database Layer


关系数据库：

PostgreSQL

保存：

- 用户
- 题目
- 定义
- 定理


图数据库：

Neo4j

保存：

- 知识关系


向量数据库：

Qdrant

保存：

- 语义搜索数据