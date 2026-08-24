-- =====================================
-- Math Knowledge Agent Database Schema
-- Version: 0.1
-- =====================================


-- =========================
-- 1. 数学知识点
-- =========================

CREATE TABLE concepts (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    description TEXT,

    field TEXT,

    level INTEGER DEFAULT 1,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);



-- =========================
-- 2. 数学定义
-- =========================

CREATE TABLE definitions (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    concept_id INTEGER,

    title TEXT NOT NULL,

    content TEXT NOT NULL,

    source TEXT,


    FOREIGN KEY(concept_id)
    REFERENCES concepts(id)

);



-- =========================
-- 3. 定理
-- =========================

CREATE TABLE theorems (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    statement TEXT NOT NULL,

    proof TEXT,


    difficulty INTEGER DEFAULT 1

);



-- =========================
-- 4. 引理
-- =========================

CREATE TABLE lemmas (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    statement TEXT,

    proof TEXT

);



-- =========================
-- 5. 数学题目
-- =========================

CREATE TABLE problems (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    question TEXT NOT NULL,

    source TEXT,

    difficulty INTEGER,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP

);



-- =========================
-- 6. 用户解答
-- =========================

CREATE TABLE solutions (

    id INTEGER PRIMARY KEY AUTOINCREMENT,


    problem_id INTEGER,


    content TEXT,


    ai_feedback TEXT,


    score INTEGER,


    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,


    FOREIGN KEY(problem_id)
    REFERENCES problems(id)

);



-- =========================
-- 7. 错误记录
-- =========================

CREATE TABLE mistakes (

    id INTEGER PRIMARY KEY AUTOINCREMENT,


    problem_id INTEGER,


    description TEXT,


    category TEXT,


    frequency INTEGER DEFAULT 1,


    FOREIGN KEY(problem_id)
    REFERENCES problems(id)

);



-- =========================
-- 8. 学习记录
-- =========================

CREATE TABLE learning_events (

    id INTEGER PRIMARY KEY AUTOINCREMENT,


    object_type TEXT,


    object_id INTEGER,


    action TEXT,


    created_at DATETIME DEFAULT CURRENT_TIMESTAMP

);