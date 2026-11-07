-- AI Agent Harness: проект основной схемы PostgreSQL.
-- Статус: черновик для обсуждения, НЕ применённая миграция.
-- Основание: storage-design.md и storage-context-engine-api.pdf.
-- Один пользователь; ID объектов передаёт приложение, seq задаёт только порядок.
-- Предназначено для пустой целевой схемы. Старый ../../schema.sql не дополняет.
-- Здесь только DDL: без данных, функций, триггеров и кода репозиториев.
-- Необязательные дополнения: schema-memory.sql и schema-llm-trace.sql.

BEGIN;

-- 1. Регистрация чатов и проектов. В рабочем API нет ChatRepo:
-- их создание и привязка пока являются отдельной процедурой настройки.
CREATE TABLE chats (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    seq         BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    name        TEXT NOT NULL,
    root_path   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT projects_root_path_not_empty CHECK (btrim(root_path) <> '')
);

CREATE TABLE chat_projects (
    chat_id     TEXT NOT NULL REFERENCES chats(id),
    project_id  TEXT NOT NULL REFERENCES projects(id),
    seq         BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    PRIMARY KEY (chat_id, project_id)
);

CREATE INDEX chat_projects_project_idx ON chat_projects (project_id, chat_id);

-- 2. TaskRepo. frame и counters сохраняются целиком по общей модели API.
-- JSONB-проверки ниже проверяют внешний тип, не заменяют валидацию Pydantic.
CREATE TABLE tasks (
    id                 TEXT PRIMARY KEY,
    chat_id            TEXT NOT NULL REFERENCES chats(id),
    user_id            TEXT NOT NULL,
    project_id         TEXT,
    request_text       TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'new',
    frame              JSONB NOT NULL DEFAULT
        '{"goal":null,"slots":{},"assumptions":[],"open_gaps":[]}'::jsonb,
    counters           JSONB NOT NULL DEFAULT
        '{"clarification_rounds":0,"questions_asked":0,"agent_steps":0,"tool_calls":0,"llm_calls":0,"tokens_in":0,"tokens_out":0}'::jsonb,
    failure            JSONB,
    context_block_ids  TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
    version            INTEGER NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tasks_status_valid CHECK (
        status IN ('new', 'analyzing', 'waiting_user', 'executing',
                   'completed', 'failed', 'cancelled')
    ),
    CONSTRAINT tasks_version_nonnegative CHECK (version >= 0),
    CONSTRAINT tasks_frame_object CHECK (jsonb_typeof(frame) = 'object'),
    CONSTRAINT tasks_counters_object CHECK (jsonb_typeof(counters) = 'object'),
    CONSTRAINT tasks_failure_object CHECK (
        failure IS NULL OR jsonb_typeof(failure) = 'object'
    ),
    CONSTRAINT tasks_context_ids_no_nulls CHECK (
        array_position(context_block_ids, NULL) IS NULL
    ),
    CONSTRAINT tasks_id_chat_unique UNIQUE (id, chat_id),
    -- При project_id = NULL выбор проекта ещё не сделан.
    -- При заполненном project_id проект обязан быть привязан к этому чату.
    CONSTRAINT tasks_chat_project_fk FOREIGN KEY (chat_id, project_id)
        REFERENCES chat_projects (chat_id, project_id)
);

CREATE UNIQUE INDEX one_active_task_per_chat ON tasks (chat_id)
    WHERE status NOT IN ('completed', 'failed', 'cancelled');

-- ВАЖНО: CAS реализуется будущим TaskRepo.update через сравнение version
-- в условии UPDATE; один столбец version сам по себе этого не обеспечивает.
-- Слот frame.slots.project_id тоже проверяется приложением: FK его не видит.

-- 3. MessageRepo. seq не является ID сообщения и не передаётся в модель API.
CREATE TABLE messages (
    id            TEXT PRIMARY KEY,
    seq           BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    chat_id       TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    role          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    content       TEXT NOT NULL,
    tool_calls    JSONB NOT NULL DEFAULT '[]'::jsonb,
    tool_call_id  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT messages_role_valid CHECK (
        role IN ('user', 'assistant', 'tool', 'system')
    ),
    CONSTRAINT messages_kind_valid CHECK (
        kind IN ('request', 'question', 'answer', 'tool_call',
                 'tool_result', 'final', 'error', 'note')
    ),
    CONSTRAINT messages_tool_calls_array CHECK (jsonb_typeof(tool_calls) = 'array'),
    CONSTRAINT messages_id_task_unique UNIQUE (id, task_id),
    CONSTRAINT messages_task_chat_fk FOREIGN KEY (task_id, chat_id)
        REFERENCES tasks (id, chat_id)
);

CREATE INDEX messages_task_seq_idx ON messages (task_id, seq);
CREATE INDEX messages_chat_seq_idx ON messages (chat_id, seq);

-- 4. ClarificationRepo: один репозиторий обслуживает ДВЕ таблицы.
-- Значения статуса вопроса взяты из сценариев PDF; сверить с исходным enum.
CREATE TABLE clarification_questions (
    id          TEXT PRIMARY KEY,
    seq         BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    gap_id      TEXT NOT NULL,
    slot_name   TEXT NOT NULL,
    text        TEXT NOT NULL,
    options     JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority    DOUBLE PRECISION NOT NULL,
    round       INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT questions_options_array CHECK (jsonb_typeof(options) = 'array'),
    CONSTRAINT questions_round_positive CHECK (round >= 1),
    CONSTRAINT questions_status_valid CHECK (status IN ('pending', 'answered', 'skipped')),
    CONSTRAINT questions_id_task_unique UNIQUE (id, task_id)
);

CREATE INDEX questions_task_seq_idx ON clarification_questions (task_id, seq);

CREATE TABLE clarification_answers (
    id              TEXT PRIMARY KEY,
    seq             BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    task_id         TEXT NOT NULL REFERENCES tasks(id),
    question_id     TEXT NOT NULL,
    value           JSONB NOT NULL,
    raw_message_id  TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Эти составные FK не дадут привязать ответ к вопросу/сообщению другой задачи.
    CONSTRAINT answers_question_task_fk FOREIGN KEY (question_id, task_id)
        REFERENCES clarification_questions (id, task_id),
    CONSTRAINT answers_message_task_fk FOREIGN KEY (raw_message_id, task_id)
        REFERENCES messages (id, task_id)
);

CREATE INDEX answers_task_seq_idx ON clarification_answers (task_id, seq);
CREATE INDEX answers_question_idx ON clarification_answers (question_id, task_id);
CREATE INDEX answers_message_idx ON clarification_answers (raw_message_id, task_id);

-- 5. ToolRunRepo. call/result содержат полные модели ToolCall/ToolResult.
CREATE TABLE tool_runs (
    id           TEXT PRIMARY KEY,
    seq          BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    task_id      TEXT NOT NULL REFERENCES tasks(id),
    step         INTEGER NOT NULL,
    call         JSONB NOT NULL,
    status       TEXT NOT NULL,
    result       JSONB,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    CONSTRAINT tool_runs_step_nonnegative CHECK (step >= 0),
    CONSTRAINT tool_runs_status_valid CHECK (
        status IN ('started', 'succeeded', 'failed', 'interrupted')
    ),
    CONSTRAINT tool_runs_call_object CHECK (jsonb_typeof(call) = 'object'),
    CONSTRAINT tool_runs_result_object CHECK (
        result IS NULL OR jsonb_typeof(result) = 'object'
    )
);

CREATE INDEX tool_runs_task_seq_idx ON tool_runs (task_id, seq);

-- 6. SnapshotRepo. Актуальное состояние читается из tasks, не из снимков.
CREATE TABLE task_snapshots (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    version     INTEGER NOT NULL,
    status      TEXT NOT NULL,
    frame       JSONB NOT NULL,
    counters    JSONB NOT NULL,
    transition  JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT snapshots_task_version_unique UNIQUE (task_id, version),
    CONSTRAINT snapshots_version_nonnegative CHECK (version >= 0),
    CONSTRAINT snapshots_status_valid CHECK (
        status IN ('new', 'analyzing', 'waiting_user', 'executing',
                   'completed', 'failed', 'cancelled')
    ),
    CONSTRAINT snapshots_frame_object CHECK (jsonb_typeof(frame) = 'object'),
    CONSTRAINT snapshots_counters_object CHECK (jsonb_typeof(counters) = 'object'),
    CONSTRAINT snapshots_transition_object CHECK (
        transition IS NULL OR jsonb_typeof(transition) = 'object'
    )
);

-- Неизменяемость снимков и запись снимка на КАЖДОЕ обновление Task —
-- правила будущих репозиториев и UoW. Триггеры здесь не вводятся.

-- 7. InboxRepo. key — глобально уникальный client_message_id по текущему API.
CREATE TABLE inbox (
    key         TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX inbox_task_idx ON inbox (task_id);

-- ProjectRepo использует projects + chat_projects, определённые выше.

-- Контекст. Не восьмой репозиторий оркестратора, а данные Context Engine.
-- Сохранение блока не даёт права доступа: права проверяются по исходному источнику.
CREATE TABLE context_blocks (
    id                 TEXT PRIMARY KEY,
    owner_user_id      TEXT NOT NULL,
    origin_scope       TEXT NOT NULL,
    origin_chat_id     TEXT REFERENCES chats(id),
    origin_project_id  TEXT REFERENCES projects(id),
    source_kind        TEXT NOT NULL,
    source_ref         TEXT NOT NULL,
    source_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    text               TEXT NOT NULL,
    summary            TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT context_origin_scope_valid CHECK (
        origin_scope IN ('chat', 'project', 'memory')
    ),
    CONSTRAINT context_chat_origin_present CHECK (
        origin_scope <> 'chat' OR origin_chat_id IS NOT NULL
    ),
    CONSTRAINT context_project_origin_present CHECK (
        origin_scope <> 'project' OR origin_project_id IS NOT NULL
    ),
    CONSTRAINT context_source_metadata_object CHECK (
        jsonb_typeof(source_metadata) = 'object'
    )
);

CREATE INDEX context_owner_chat_idx ON context_blocks (owner_user_id, origin_chat_id);
CREATE INDEX context_owner_project_idx ON context_blocks (owner_user_id, origin_project_id);

-- В tasks.context_block_ids хранятся логические ссылки, НЕ внешние ключи.
-- Их существование и порядок проверяет приложение. Блоки не удаляются рабочим API.
-- source_ref также является ссылкой приложения: message:<id>, file:<путь>, memory:<id>.
-- Версия файла, диапазон строк и другие детали источника — в source_metadata.
-- score/tokens зависят от запроса и токенизатора: постоянных колонок для них нет.
-- SHA-256 не хранится и не вычисляется этим DDL. Обязательное поле API требует
-- отдельного решения команды: считать при выдаче либо изменить контракт.
-- Здесь НЕТ SQL-защиты доступа к чужому проекту: её обеспечивает Context Engine.

COMMIT;
