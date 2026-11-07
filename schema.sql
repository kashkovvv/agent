-- AI Agent Harness — схема хранения (MVP)
-- PostgreSQL, один пользователь, локально.
-- Таблицы users нет: при переходе на нескольких пользователей
-- добавим её и user_id в projects / chats.

-- ============ Проекты и чаты ============

CREATE TABLE projects (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    root_path   TEXT,                 -- локальный путь к коду проекта
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chats (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Чат может быть привязан к нескольким проектам (пример «Какой проект проверить?»).
-- «Другие чаты» для Context Engine = чаты, у которых есть общий проект.
CREATE TABLE chat_projects (
    chat_id     BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    project_id  BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (chat_id, project_id)
);

-- ============ Задачи и сообщения ============

CREATE TABLE tasks (
    id                   BIGSERIAL PRIMARY KEY,
    chat_id              BIGINT NOT NULL REFERENCES chats(id),
    project_id           BIGINT REFERENCES projects(id),  -- NULL, пока проект не выбран/не уточнён
    status               TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new','analyzing','waiting_user','executing','completed','failed')),
    goal                 TEXT,             -- цель, как её понял анализ
    clarification_round  INT  NOT NULL DEFAULT 0,
    test_case_id         TEXT,             -- необязательно: ссылка на строку в таблице экспериментов
    error                TEXT,             -- причина failed
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at          TIMESTAMPTZ
);

CREATE TABLE messages (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL REFERENCES chats(id),
    task_id     BIGINT REFERENCES tasks(id),
    role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
    kind        TEXT NOT NULL DEFAULT 'other'
        CHECK (kind IN ('request','question','answer','result','other')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON messages (chat_id, created_at);

-- ============ Контекст ============

-- Блок = фрагмент текста + откуда он взят.
CREATE TABLE context_blocks (
    id               BIGSERIAL PRIMARY KEY,
    project_id       BIGINT REFERENCES projects(id),
    chat_id          BIGINT REFERENCES chats(id),
    content          TEXT NOT NULL,
    kind             TEXT NOT NULL
        CHECK (kind IN ('message','file','note','decision','summary')),
    source_ref       JSONB NOT NULL,   -- {"message_id": 12} | {"path": "tests/x.py", "commit": "a1b2c3"}
    parent_block_id  BIGINT REFERENCES context_blocks(id),  -- для summary: из чего сделан
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON context_blocks (project_id);

-- Какие блоки Context Engine отобрал для задачи.
CREATE TABLE task_context (
    task_id    BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    block_id   BIGINT NOT NULL REFERENCES context_blocks(id),
    relevance  REAL,
    PRIMARY KEY (task_id, block_id)
);

-- ============ Clarification Engine ============

-- Параметры задачи = пробелы. Допущения — это параметры со status = 'assumed'.
CREATE TABLE task_parameters (
    id               BIGSERIAL PRIMARY KEY,
    task_id          BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,        -- 'project', 'test_command', ...
    description      TEXT,
    is_critical      BOOLEAN NOT NULL,
    status           TEXT NOT NULL DEFAULT 'missing'
        CHECK (status IN ('missing','filled','assumed')),
    value            TEXT,
    source           TEXT CHECK (source IN ('context','user','assumption')),
    source_block_id  BIGINT REFERENCES context_blocks(id),  -- если найдено в контексте
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, name)
);

CREATE TABLE clarification_questions (
    id                BIGSERIAL PRIMARY KEY,
    task_id           BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    parameter_id      BIGINT REFERENCES task_parameters(id),
    round             INT  NOT NULL,       -- номер итерации уточнения
    rank              INT  NOT NULL,       -- место в Top K внутри раунда
    text              TEXT NOT NULL,
    priority          REAL,
    priority_factors  JSONB,               -- {"blocking":1,"information_gain":0.7,"impact":0.5,...}
    status            TEXT NOT NULL DEFAULT 'asked'
        CHECK (status IN ('asked','answered','obsolete')),
    message_id        BIGINT REFERENCES messages(id),  -- сообщение, в котором задан вопрос
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clarification_answers (
    id           BIGSERIAL PRIMARY KEY,
    question_id  BIGINT NOT NULL REFERENCES clarification_questions(id) ON DELETE CASCADE,
    message_id   BIGINT NOT NULL REFERENCES messages(id),  -- одно сообщение может отвечать на несколько вопросов
    text         TEXT NOT NULL,           -- извлечённый ответ на конкретный вопрос
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ Выполнение ============

-- Полные запросы и ответы LLM.
CREATE TABLE llm_calls (
    id             BIGSERIAL PRIMARY KEY,
    task_id        BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    purpose        TEXT NOT NULL
        CHECK (purpose IN ('analyze','clarify','execute','respond')),
    model          TEXT NOT NULL,
    request        JSONB NOT NULL,         -- system + messages + tools целиком
    response       JSONB,
    input_tokens   INT,
    output_tokens  INT,
    latency_ms     INT,
    error          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Какие блоки контекста попали в конкретный промпт.
CREATE TABLE llm_call_blocks (
    llm_call_id  BIGINT NOT NULL REFERENCES llm_calls(id) ON DELETE CASCADE,
    block_id     BIGINT NOT NULL REFERENCES context_blocks(id),
    position     INT NOT NULL,
    PRIMARY KEY (llm_call_id, block_id)
);

CREATE TABLE tool_runs (
    id           BIGSERIAL PRIMARY KEY,
    task_id      BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    llm_call_id  BIGINT REFERENCES llm_calls(id),   -- какой вызов LLM предложил инструмент
    tool_name    TEXT NOT NULL,
    args         JSONB NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('ok','invalid_args','error')),
    result       JSONB,
    error        TEXT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ
);

-- ============ Состояние ============

-- Снимок на каждом переходе статуса; нужен для продолжения после паузы (не для replay).
CREATE TABLE task_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,
    state       JSONB NOT NULL,   -- цель, параметры, открытые вопросы, раунд, id последнего llm_call
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON task_snapshots (task_id, created_at DESC);
