# AI Agent Harness — оркестрация и API модулей

Онлайн-версия (редактируемая): https://claude.ai/artifact/DyUpMvXrGhCMWvDMf45BdK

## Команда

| Участник | Зона ответственности | Папка | Цвет на схемах |
| --- | --- | --- | --- |
| Сергей | оркестрация | `orchestration/` | синий |
| Егор | хранение и управление данными (Storage + Context Engine) | `data-storage/` | оранжевый |
| Родион | генерация уточняющих вопросов (Clarification Engine) | `question-generation/` | зелёный |

## Структура

```
harness_docs/
├── orchestration/                         # Сергей
│   ├── orchestration.pdf
│   ├── architecture-deep-dive.pdf
│   ├── mentor-summary.pdf
│   └── diagrams/
│       ├── 1-call-sequence.png
│       ├── 2-incoming-message.png
│       ├── 3-main-loop.png
│       └── 4-task-statuses.png
├── data-storage/                          # Егор
│   └── storage-context-engine-api.pdf
└── question-generation/                   # Родион
    └── clarification-engine-api.pdf
```

## Файлы

| Файл | Для кого | Что внутри |
| --- | --- | --- |
| `orchestration/orchestration.pdf` | вся команда | схема оркестрации (3 диаграммы), зоны ответственности, модели данных, внешнее API, конечный автомат, agent loop, восстановление, лимиты, план и открытые вопросы |
| `orchestration/architecture-deep-dive.pdf` | вся команда | подробный разбор архитектуры и оркестратора с нуля |
| `orchestration/mentor-summary.pdf` | ментор | краткая версия документа по оркестрации |
| `orchestration/diagrams/` | — | те же схемы отдельными картинками |
| `data-storage/storage-context-engine-api.pdf` | Егор | что оркестратор ждёт от Storage + Context Engine: когда вызываются, сигнатуры, гарантии, предлагаемая схема таблиц, вопросы |
| `question-generation/clarification-engine-api.pdf` | Родион | что оркестратор ждёт от Clarification Engine: когда вызывается, вход/выход, что оркестратор делает с ответом, правила, пример JSON, вопросы |

## Схемы

1. `1-call-sequence.png` — кто кого вызывает в сценарии «Проверь тесты проекта».
2. `2-incoming-message.png` — куда попадает сообщение пользователя.
3. `3-main-loop.png` — шаг анализа и шаг выполнения.
4. `4-task-statuses.png` — конечный автомат статусов.
