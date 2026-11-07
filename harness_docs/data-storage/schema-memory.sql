-- НЕОБЯЗАТЕЛЬНОЕ дополнение к schema.sql: явные заметки памяти.
-- Предложение для обсуждения. Отдельного MemoryRepo в API пока нет.
-- Применять только после согласования семантики памяти и процедуры её записи.

BEGIN;

CREATE TABLE memory_entries (
    id             TEXT PRIMARY KEY,
    owner_user_id  TEXT NOT NULL,
    scope          TEXT NOT NULL,
    chat_id        TEXT REFERENCES chats(id),
    project_id     TEXT REFERENCES projects(id),
    text           TEXT NOT NULL,
    source_ref     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT memory_scope_valid CHECK (
        scope IN ('personal', 'chat', 'project')
    ),
    CONSTRAINT memory_scope_matches_target CHECK (
        (scope = 'personal' AND chat_id IS NULL AND project_id IS NULL)
        OR (scope = 'chat' AND chat_id IS NOT NULL AND project_id IS NULL)
        OR (scope = 'project' AND project_id IS NOT NULL AND chat_id IS NULL)
    )
);

CREATE INDEX memory_owner_chat_idx ON memory_entries (owner_user_id, chat_id);
CREATE INDEX memory_owner_project_idx ON memory_entries (owner_user_id, project_id);

-- context_blocks.source_ref = memory:<id> — логическая ссылка на заметку.
-- Выбранный текст блока сохраняется отдельно, чтобы изменение заметки
-- не переписало уже показанный модели контекст.
-- Проверка owner_user_id и разрешений — задача Context Engine, а не CHECK.

COMMIT;
