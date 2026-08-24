-- Math Knowledge Agent Database


-- 数学概念表
CREATE TABLE concepts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    field TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 定义表
CREATE TABLE definitions (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    concept_id INTEGER,

    FOREIGN KEY(concept_id)
    REFERENCES concepts(id)
);


-- 定理表
CREATE TABLE theorems (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    statement TEXT NOT NULL,
    proof TEXT,

    difficulty INTEGER
);


-- 题目表
CREATE TABLE problems (
    id INTEGER PRIMARY KEY,
    question TEXT NOT NULL,
    source TEXT,
    difficulty INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 用户解答表
CREATE TABLE solutions (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER,

    content TEXT,
    ai_feedback TEXT,

    FOREIGN KEY(problem_id)
    REFERENCES problems(id)
);


-- 错误记录表
CREATE TABLE mistakes (
    id INTEGER PRIMARY KEY,

    description TEXT,
    category TEXT,
    frequency INTEGER DEFAULT 1
);