-- НЕОБЯЗАТЕЛЬНОЕ дополнение к schema.sql: точные LLM-запросы и ответы.
-- Пока нет согласованного интерфейса передачи этих записей от LLM-адаптера.
-- Таблицы сами по себе не включают трассировку: требуется отдельное решение команды.

BEGIN;

CREATE TABLE llm_calls (
    id             TEXT PRIMARY KEY,
    task_id        TEXT NOT NULL REFERENCES tasks(id),
    purpose        TEXT NOT NULL,
    model          TEXT NOT NULL,
    attempt        INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'started',
    request        JSONB NOT NULL,
    response       JSONB,
    error          TEXT,
    input_tokens   BIGINT,
    output_tokens  BIGINT,
    duration_ms    BIGINT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    CONSTRAINT llm_calls_id_task_unique UNIQUE (id, task_id),
    CONSTRAINT llm_calls_purpose_valid CHECK (
        purpose IN ('assess', 'parse_answers', 'execute')
    ),
    CONSTRAINT llm_calls_status_valid CHECK (
        status IN ('started', 'succeeded', 'failed', 'interrupted')
    ),
    CONSTRAINT llm_calls_attempt_positive CHECK (attempt >= 1),
    CONSTRAINT llm_calls_request_object CHECK (jsonb_typeof(request) = 'object'),
    CONSTRAINT llm_calls_input_tokens_nonnegative CHECK (input_tokens >= 0),
    CONSTRAINT llm_calls_output_tokens_nonnegative CHECK (output_tokens >= 0),
    CONSTRAINT llm_calls_duration_nonnegative CHECK (duration_ms >= 0)
);

CREATE INDEX llm_calls_task_time_idx ON llm_calls (task_id, started_at, id);

CREATE TABLE llm_call_blocks (
    llm_call_id  TEXT NOT NULL REFERENCES llm_calls(id),
    position     INTEGER NOT NULL,
    block_id     TEXT NOT NULL REFERENCES context_blocks(id),
    PRIMARY KEY (llm_call_id, position),
    CONSTRAINT llm_call_blocks_position_nonnegative CHECK (position >= 0)
);

CREATE INDEX llm_call_blocks_block_idx ON llm_call_blocks (block_id);

-- Необязательная ссылка запуска инструмента на предложивший его LLM-вызов.
-- task_id в составном FK запрещает связать записи разных задач.
ALTER TABLE tool_runs ADD COLUMN llm_call_id TEXT;
ALTER TABLE tool_runs ADD CONSTRAINT tool_runs_llm_call_task_fk
    FOREIGN KEY (llm_call_id, task_id) REFERENCES llm_calls (id, task_id);

-- Каждая сетевая попытка — отдельная запись. position — с нуля, в порядке
-- включения блоков в конкретный запрос; один блок может встретиться несколько раз.
-- Все семь базовых репозиториев остаются прежними: канал записи трассировки
-- надо спроектировать отдельно, не добавлять запись в БД в Clarification Engine.

COMMIT;
