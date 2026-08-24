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