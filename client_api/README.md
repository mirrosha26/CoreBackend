# Документация Client API

Client API — RESTful интерфейс, предназначенный для интеграции в системы мониторинга венчурного капитала. Обеспечивает доступ к данным об инвесторах, проектах, ключевых лицах и рыночных сигналах из венчурной экосистемы.

**Базовый URL:** `http://localhost:8000/client_api/`

**Аутентификация:** `Authorization: Token <your_token>`

Все эндпоинты требуют аутентификации через токен в заголовке `Authorization`.

---

## Карточки

### Получить список карточек

**GET** `/v1/cards/`

Получить список сигнальных карточек (проектов) с поддержкой пагинации, сортировки и фильтрации.

#### Основные параметры

- `limit` (integer) — количество записей на странице (максимум 100, по умолчанию 20)
- `offset` (integer) — смещение от начала списка (по умолчанию 0)
- `sort` (string) — сортировка: предустановленные значения или пользовательский формат (по умолчанию: `latest_signal_date:desc`)
  - **Предустановленные значения:**
    - `trending` — сортировка по количеству взаимодействий (по убыванию), затем по дате последнего сигнала (по убыванию)
    - `recent` — сортировка по дате создания (по убыванию)
    - `most_active` — сортировка по дате обновления (по убыванию), затем по количеству взаимодействий (по убыванию)
  - **Пользовательский формат:** `поле:направление` или несколько полей `поле1:направление1,поле2:направление2`
  - **Доступные поля для карточек:** `created_at`, `updated_at`, `name`, `interactions_count`, `latest_signal_date`
  - **Направления:** `asc` (по возрастанию) или `desc` (по убыванию)
  - **Примеры:** 
    - `sort=name:asc` — сортировка по имени по возрастанию
    - `sort=created_at:desc,interactions_count:desc` — сначала по дате создания (по убыванию), затем по количеству взаимодействий (по убыванию)
- `include_user_data` (boolean) — включает пользовательские данные (избранное, заметки, папки)

#### Фильтры

- `stages` (string) — фильтр по стадиям (через запятую): `stages=seed,series_a`. Получить доступные стадии [здесь](#стадии)
- `rounds` (string) — фильтр по раундам (через запятую): `rounds=raising_now,just_raised`. Получить доступные раунды [здесь](#раунды)
- `categories` (string) — фильтр по категориям (через запятую): `categories=ai,saas`. Получить доступные категории [здесь](#категории)
- `participants` (string) — фильтр по участникам (через запятую): `participants=investor-fund`. Получить доступных участников [здесь](#участники)
- `filter_id` (integer) — применить сохраненный фильтр пользователя. Получить доступные фильтры [здесь](#сохраненные-фильтры)
- `folder_ids` (string) — фильтр по папкам (через запятую): `folder_ids=1,2,3`. Получить доступные папки [здесь](#папки-пользователя)

#### Фильтры по датам

- `created_after`, `created_before` — фильтр по дате создания (формат: YYYY-MM-DD)
- `updated_after`, `updated_before` — фильтр по дате обновления
- `last_interaction_after`, `last_interaction_before` — фильтр по дате последнего взаимодействия
- `first_interaction_after`, `first_interaction_before` — фильтр по дате первого взаимодействия

#### Логика фильтрации

- Разные группы фильтров объединяются через **AND** (кроме стадий и раундов)
- Значения внутри каждой группы объединяются через **OR**
- **Стадии и раунды объединяются через OR** — если указаны и `stages`, и `rounds`, будут возвращены карточки, соответствующие либо стадии, либо раунду
- При указании родительской категории автоматически включаются все дочерние категории

**Примеры:**
- `stages=seed&rounds=raising_now` — возвращает карточки со стадией `seed` **ИЛИ** раундом `raising_now`
- `stages=seed,series_a&categories=ai` — возвращает карточки со стадией `seed` **ИЛИ** `series_a`, **И** категорией `ai`

#### Пример запроса

```http
GET /v1/cards/?limit=20&offset=0&sort=trending&categories=ai,saas&stages=seed
Authorization: Token <your_token>
```

#### Пример ответа

```json
{
  "data": [
    {
      "id": 1,
      "slug": "project-slug",
      "name": "Project Name",
      "public_url": "https://app.example.com/public/project-slug",
      "interactions_count": 15,
      "trending": true,
      "description": "Project description",
      "image": "https://app.example.com/media/...",
      "url": "https://example.com",
      "stage": {
        "name": "Seed",
        "slug": "seed"
      },
      "round": {
        "name": "Seed Round",
        "slug": "seed"
      },
      "categories": [
        {
          "name": "SaaS",
          "slug": "saas"
        }
      ],
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:45:00Z",
      "last_round": "2024-01-10",
      "last_interaction_at": "2024-01-20T12:00:00Z",
      "social_links": [
        {
          "key": "twitter",
          "name": "twitter",
          "url": "https://x.com/project"
        }
      ],
      "user_data": {
        "is_liked": false,
        "has_note": false,
        "note": null,
        "folders": []
      }
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "has_next": true
  }
}
```

---

### Получить список карточек (POST)

**POST** `/v1/cards/`

Получить список карточек с фильтрами через JSON body (полезно для больших объемов фильтров).

**Важно:** Метод POST принимает те же параметры, что и GET, но в JSON body. Это полезно для больших объемов фильтров (тысячи категорий, участников и т.д.), которые не помещаются в URL.

#### Параметры запроса (JSON Body)

Все параметры такие же, как в методе GET, но передаются в JSON body. Списки передаются как массивы, а не как строки через запятую:

- `limit` (integer) — количество записей на странице (максимум 100, по умолчанию 20)
- `offset` (integer) — смещение от начала списка (по умолчанию 0)
- `sort` (string) — сортировка: `trending`, `recent`, `most_active` или пользовательский формат `поле:направление`
- `include_user_data` (boolean) — включает пользовательские данные (избранное, заметки, папки)
- `stages` (array[string]) — фильтр по стадиям (массив): `["seed", "series_a"]`
- `rounds` (array[string]) — фильтр по раундам (массив): `["raising_now", "just_raised"]`
- `categories` (array[string]) — фильтр по категориям (массив): `["ai", "saas"]`
- `participants` (array[string]) — фильтр по участникам (массив): `["investor-fund"]`
- `filter_id` (integer) — применить сохраненный фильтр пользователя
- `folder_ids` (array[integer]) — фильтр по папкам (массив): `[1, 2, 3]`
- `created_after`, `created_before` (string) — фильтр по дате создания (формат: YYYY-MM-DD)
- `updated_after`, `updated_before` (string) — фильтр по дате обновления
- `last_interaction_after`, `last_interaction_before` (string) — фильтр по дате последнего взаимодействия
- `first_interaction_after`, `first_interaction_before` (string) — фильтр по дате первого взаимодействия

#### Пример запроса

**Базовый POST запрос:**

```http
POST /v1/cards/
Content-Type: application/json
Authorization: Token <your_token>

{
  "limit": 20,
  "offset": 0,
  "sort": "recent"
}
```

**POST с большим объемом фильтров:**

```http
POST /v1/cards/
Content-Type: application/json
Authorization: Token <your_token>

{
  "limit": 50,
  "offset": 0,
  "sort": "trending",
  "stages": ["seed", "series_a", "series_b"],
  "categories": ["ai", "saas", "b2b", "fintech", "healthcare"],
  "participants": ["investor-fund-1", "investor-fund-2", "investor-fund-3"],
  "created_after": "2024-01-01",
  "folder_ids": [1, 2, 3, 4, 5]
}
```

**POST с пользовательской сортировкой:**

```http
POST /v1/cards/
Content-Type: application/json
Authorization: Token <your_token>

{
  "limit": 20,
  "offset": 0,
  "sort": "name:asc,created_at:desc",
  "categories": ["ai", "saas"]
}
```

**Примечание:** Пользовательская сортировка передается как строка в формате `поле:направление,поле:направление` (тот же формат, что и в GET запросе). Например:
- `"sort": "name:asc"` — сортировка по имени по возрастанию
- `"sort": "created_at:desc,interactions_count:desc"` — сначала по дате создания (по убыванию), затем по количеству взаимодействий (по убыванию)

#### Пример ответа

Формат ответа идентичен методу GET (см. выше).

---

### Получить карточку по slug

**GET** `/v1/cards/<slug>/`

Получить детальную информацию о конкретной карточке по её slug.

#### Параметры

- `include_user_data` (boolean) — включает пользовательские данные

#### Пример запроса

```http
GET /v1/cards/project-slug/?include_user_data=true
Authorization: Token <your_token>
```

#### Пример ответа

```json
{
  "data": {
    "id": 1,
    "slug": "project-slug",
    "name": "Project Name",
    "public_url": "https://app.example.com/public/project-slug",
    "interactions_count": 15,
    "trending": true,
    "description": "Detailed project description",
    "image": "https://app.example.com/media/...",
    "url": "https://example.com",
    "stage": {
      "name": "Seed",
      "slug": "seed"
    },
    "round": {
      "name": "Seed Round",
      "slug": "seed"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T14:45:00Z",
    "last_round": "2024-01-10",
    "last_interaction_at": "2024-01-20T12:00:00Z",
    "first_interaction_at": "2024-01-15T10:30:00Z",
    "categories": [
      {
        "name": "SaaS",
        "slug": "saas"
      }
    ],
    "social_links": [
      {
        "key": "twitter",
        "name": "twitter",
        "url": "https://x.com/project"
      }
    ],
    "user_data": {
      "is_liked": true,
      "has_note": true,
      "note": {
        "text": "Interesting project",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-20T14:45:00Z"
      },
      "folders": [
        {"id": 1, "name": "Favorites"}
      ]
    },
    "team_members": [],
    "more": null,
    "employment_data": null,
    "interactions": [
      {
        "id": 1,
        "created_at": "2024-01-20T12:00:00Z",
        "participant": {
          "name": "Investor Fund",
          "slug": "investor-fund",
          "type": "fund"
        },
        "associated_participant": {
          "name": "John Doe",
          "slug": "john-doe",
          "type": "investor"
        }
      }
    ],
    "has_more_interactions": false
  }
}
```

---

### Получить взаимодействия карточки

**GET** `/v1/cards/<slug>/interactions/`

Получить все взаимодействия (сигналы) для карточки с пагинацией.

#### Параметры

- `limit` (integer) — количество записей (максимум 200, по умолчанию 50)
- `offset` (integer) — смещение от начала списка (по умолчанию 0)

#### Пример запроса

```http
GET /v1/cards/project-slug/interactions/?limit=50&offset=0
Authorization: Token <your_token>
```

#### Пример ответа

```json
{
  "data": [
    {
      "id": 1001,
      "created_at": "2024-01-20T12:00:00Z",
      "participant": {
        "name": "Investor Fund",
        "slug": "investor-fund",
        "type": "fund"
      },
      "associated_participant": {
        "name": "John Doe",
        "slug": "john-doe",
        "type": "investor"
      }
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 400,
    "has_next": true
  }
}
```

---

### Справочные данные

Все справочные значения (стадии, раунды, категории, типы участников, папки, фильтры) должны быть получены через мета-эндпоинты, перечисленные ниже. Эти эндпоинты предоставляют полный список доступных значений и их slugs/ID для фильтрации и отображения.

**Важно:** Все справочные эндпоинты требуют аутентификации через токен в заголовке `Authorization`.

#### Категории

**GET** `/v1/cards/categories/` {#категории}

Получить иерархическую структуру категорий (родительские и дочерние категории).

**Требуется аутентификация:** Да

**Пример ответа:**

```json
{
  "data": [
    {
      "name": "AI",
      "slug": "ai",
      "categories": [
        {
          "name": "Machine Learning",
          "slug": "machine_learning"
        },
        {
          "name": "Computer Vision",
          "slug": "computer_vision"
        }
      ]
    },
    {
      "name": "B2B",
      "slug": "b2b",
      "categories": [
        {
          "name": "SaaS",
          "slug": "saas"
        }
      ]
    }
  ]
}
```

#### Стадии

**GET** `/v1/cards/stages/` {#стадии}

Получить список стадий развития проектов (seed, series_a, series_b и т.д.).

**Требуется аутентификация:** Да

**Пример ответа:**

```json
{
  "data": [
    {
      "slug": "unknown",
      "name": "Unknown"
    },
    {
      "slug": "seed",
      "name": "Seed"
    },
    {
      "slug": "series_a",
      "name": "Series A"
    }
  ]
}
```

#### Раунды

**GET** `/v1/cards/rounds/` {#раунды}

**Требуется аутентификация:** Да

Получить список раундов финансирования (raising_now, just_raised, about_to_raise и т.д.).

**Пример ответа:**

```json
{
  "data": [
    {
      "slug": "just_raised",
      "name": "Just Raised"
    },
    {
      "slug": "raising_now",
      "name": "Raising Now"
    },
    {
      "slug": "about_to_raise",
      "name": "About to Raise"
    }
  ]
}
```

#### Папки пользователя

**Требуется аутентификация:** Да

**GET** `/v1/cards/folders/` {#папки-пользователя}

Получить список папок пользователя с количеством карточек в каждой.

**Пример ответа:**

```json
{
  "data": [
    {
      "id": 1,
      "name": "Favorites",
      "is_default": true,
      "cards_count": 25
    },
    {
      "id": 90,
      "name": "AI Projects",
      "is_default": false,
      "cards_count": 12
    }
  ]
}
```

**Требуется аутентификация:** Да

#### Сохраненные фильтры

**GET** `/v1/cards/filters/` {#сохраненные-фильтры}

Получить список сохраненных фильтров пользователя (для применения через `filter_id`).

**Пример ответа:**

```json
{
  "data": [
    {
      "id": 8,
      "name": "Web3"
    },
    {
      "id": 123,
      "name": "AI & SaaS Projects"
    }
  ]
}
```

---

## Участники

### Получить список участников

**GET** `/v1/participants/`

Получить список участников (фонды, инвесторы, ангелы) с пагинацией и фильтрацией.

#### Основные параметры

- `limit` (integer) — количество записей на странице (максимум 200, по умолчанию 50)
- `offset` (integer) — смещение от начала списка (по умолчанию 0)
- `search` (string) — поиск по имени и описанию
- `sort` (string) — сортировка: предустановленные значения или пользовательский формат
  - **Предустановленные значения:**
    - `name` (по умолчанию) — сортировка по имени по возрастанию
    - `most_active` — сортировка по месячным сигналам (по убыванию), затем по имени (по возрастанию)
  - **Пользовательский формат:** `поле:направление` или несколько полей `поле1:направление1,поле2:направление2`
  - **Доступные поля для участников:** `name`, `monthly_signals`
  - **Направления:** `asc` (по возрастанию) или `desc` (по убыванию)
  - **Примеры:**
    - `sort=name:asc` — сортировка по имени по возрастанию
    - `sort=monthly_signals:desc,name:asc` — сначала по месячным сигналам (по убыванию), затем по имени (по возрастанию)
- `include_user_data` (boolean) — включает пользовательские данные (is_saved)

#### Фильтры

- `type` (string) — фильтр по типу: `fund`, `investor`, `angel` и т.д. Получить доступные типы [здесь](#типы-участников)
- `saved_only` (boolean) — показать только сохраненных участников

#### Пример запроса

```http
GET /v1/participants/?limit=50&offset=0&type=fund&sort=most_active
Authorization: Token <your_token>
```

#### Пример ответа

```json
{
  "data": [
    {
      "slug": "investor-fund",
      "name": "Investor Fund",
      "alt_name": "VC",
      "email": "contact@investorfund.com",
      "image": "https://app.example.com/media/participants/investor-fund/image.jpg",
      "type": "fund",
      "about": "Leading venture capital fund focused on B2B SaaS companies",
      "monthly_signals": 15,
      "associated_with": {
        "slug": "parent-fund",
        "name": "Parent Fund"
      },
      "self_associated": false,
      "is_saved": true
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 150,
    "has_next": true
  }
}
```

**Примечание:** Поле `is_saved` появляется только когда в запросе указан `include_user_data=true`.

---

### Получить участника по slug

**GET** `/v1/participants/<slug>/`

Получить детальную информацию об участнике по slug.

#### Параметры

- `include_user_data` (boolean) — включает пользовательские данные

#### Пример запроса

```http
GET /v1/participants/investor-fund/?include_user_data=true
Authorization: Token <your_token>
```

#### Пример ответа

```json
{
  "data": {
    "slug": "investor-fund",
    "name": "Investor Fund",
    "alt_name": "VC",
    "email": "contact@investorfund.com",
    "image": "https://app.example.com/media/participants/investor-fund/image.jpg",
    "type": "fund",
    "about": "Leading venture capital fund focused on B2B SaaS companies",
    "monthly_signals": 15,
    "associated_with": {
      "slug": "parent-fund",
      "name": "Parent Fund"
    },
    "self_associated": false,
    "sources": [
      {
        "slug": "investorfund",
        "type": "twitter",
        "link": "https://twitter.com/investorfund"
      },
      {
        "slug": "investor-fund",
        "type": "linkedin",
        "link": "https://linkedin.com/company/investor-fund"
      }
    ]
  }
}
```

---

### Получить несколько участников

**GET** `/v1/participants/batch/`

Получить несколько участников по списку slugs (пакетная операция, максимум 100).

#### Параметры

- `slugs` (string, обязательный) — список slugs через запятую: `slugs=investor-fund,john-doe`
- `include_user_data` (boolean) — включает пользовательские данные

#### Пример запроса

```http
GET /v1/participants/batch/?slugs=investor-fund,john-doe,another-fund
Authorization: Token <your_token>
```

#### Пример ответа

```json
{
  "data": [
    {
      "slug": "investor-fund",
      "name": "Investor Fund",
      "alt_name": "VC",
      "email": "contact@investorfund.com",
      "image": "https://app.example.com/media/participants/investor-fund/image.jpg",
      "type": "fund",
      "about": "Leading venture capital fund focused on B2B SaaS companies",
      "monthly_signals": 15,
      "associated_with": {
        "slug": "parent-fund",
        "name": "Parent Fund"
      },
      "self_associated": false,
      "sources": []
    },
    {
      "slug": "john-doe",
      "name": "John Doe",
      "alt_name": null,
      "email": "john@example.com",
      "image": "https://app.example.com/media/participants/john-doe/image.jpg",
      "type": "investor",
      "about": "Angel investor and advisor",
      "monthly_signals": 8,
      "associated_with": null,
      "self_associated": false,
      "sources": []
    }
  ],
  "requested": 2,
  "found": 2
}
```

**Требуется аутентификация:** Да

---

### Типы участников

**GET** `/v1/participants/types/` {#типы-участников}

Получить список типов участников (fund, investor, angel, founder, accelerator и т.д.).

**Пример ответа:**

```json
{
  "data": [
    {
      "slug": "fund",
      "name": "Fund"
    },
    {
      "slug": "investor",
      "name": "Investor"
    },
    {
      "slug": "angel",
      "name": "Angel Investor"
    },
    {
      "slug": "founder",
      "name": "Founder"
    },
    {
      "slug": "accelerator",
      "name": "Accelerator"
    }
  ]
}

**Требуется аутентификация:** Да (токен проверяется в процессе запроса)
```


---

## Аутентификация

### Проверка токена

**GET** `/v1/token/validate/`

Проверить токен аутентификации.

**Требуется аутентификация:** Да (токен проверяется в процессе запроса)

#### Пример запроса

```http
GET /v1/token/validate/
Authorization: Token <your_token>
```

#### Успешный ответ (200 OK)

```json
{
  "valid": true,
  "message": "Token is valid",
  "user": {
    "username": "user@example.com",
    "email": "user@example.com"
  }
}
```

---

## Словарь терминов

Полное описание всех атрибутов, возвращаемых API.

### Атрибуты карточки

#### Базовые поля

- **`id`** (integer, обязательно) — Уникальный идентификатор карточки
- **`slug`** (string, обязательно) — URL-дружественный идентификатор, используемый в запросах API (например, `thinkymachines`)
- **`name`** (string, обязательно) — Название проекта/компании или имя человека
- **`public_url`** (string, обязательно) — Публичный URL для просмотра карточки на платформе (например, `https://app.example.com/public/thinkymachines`)
- **`description`** (string|null) — Подробное описание проекта
- **`image`** (string|null) — Абсолютный URL изображения/логотипа проекта
- **`url`** (string|null) — URL веб-сайта проекта или аккаунта человека

#### Статус и метрики

- **`interactions_count`** (integer, обязательно) — Общее количество сигналов/взаимодействий для этой карточки
- **`trending`** (boolean, обязательно) — Является ли карточка популярной в данный момент (на основе недавней активности)
- **`stage`** (object, обязательно) — Стадия развития проекта
  - `name` (string) — Человекочитаемое название стадии (например, "Seed", "Unknown")
  - `slug` (string|null) — Идентификатор стадии для фильтрации (например, `seed`)
  - Получить доступные стадии [здесь](#стадии)
- **`round`** (object, обязательно) — Текущий статус раунда финансирования
  - `name` (string) — Человекочитаемое название раунда (например, "Unknown", "Raising Now")
  - `slug` (string|null) — Идентификатор раунда для фильтрации (например, `unknown`, `raising_now`)
  - Получить доступные раунды [здесь](#раунды)

#### Категории

- **`categories`** (array, обязательно) — Список категорий, к которым относится проект
  - Каждый элемент содержит:
    - `name` (string) — Название категории (например, "AI", "Open Source")
    - `slug` (string) — Идентификатор категории для фильтрации (например, `ai`, `open-source-main`)
  - Получить доступные категории [здесь](#категории)
  - Категории иерархические (при фильтрации родительские категории автоматически включают все дочерние)

#### Даты

- **`created_at`** (string, обязательно) — ISO 8601 UTC datetime создания карточки (например, `2025-02-18T19:31:19Z`)
- **`updated_at`** (string, обязательно) — ISO 8601 UTC datetime последнего обновления карточки (например, `2025-07-21T14:04:01Z`)
- **`last_round`** (string|null) — Дата последнего раунда финансирования в формате `YYYY-MM-DD` (например, `2025-06-20`)
- **`last_interaction_at`** (string|null) — ISO 8601 UTC datetime самого недавнего сигнала/взаимодействия (например, `2025-11-14T16:16:29Z`)
- **`first_interaction_at`** (string|null) — ISO 8601 UTC datetime первого сигнала/взаимодействия (например, `2025-02-18T19:30:18Z`)

#### Социальные ссылки

- **`social_links`** (array, обязательно) — Список ссылок на социальные сети
  - Каждый элемент содержит:
    - `key` (string) — Нормализованный идентификатор платформы (например, "twitter")
    - `name` (string) — Название платформы (например, "twitter")
    - `url` (string) — Полный URL профиля в социальной сети (например, `https://x.com/thinkymachines`)

#### Пользовательские данные (когда `include_user_data=true`)

- **`user_data`** (object, опционально) — Пользовательские данные для аутентифицированного пользователя
  - `is_liked` (boolean) — Лайкнул ли пользователь/добавил ли в избранное эту карточку
  - `has_note` (boolean) — Создал ли пользователь заметку для этой карточки
  - `note` (object|null) — Объект заметки пользователя (присутствует только если `has_note=true`)
    - `text` (string) — Текст заметки
    - `created_at` (string) — ISO 8601 UTC datetime создания заметки
    - `updated_at` (string) — ISO 8601 UTC datetime последнего обновления заметки
  - `folders` (array[object]) — Список папок, в которых сохранена эта карточка
    - Каждый элемент содержит:
      - `id` (integer) — ID папки
      - `name` (string) — Название папки

#### Дополнительные поля детального представления

- **`team_members`** (array) — Список членов команды (только в детальном представлении)
- **`more`** (object) — Дополнительная информация о проекте (только в детальном представлении)
- **`employment_data`** (object) — Информация о занятости (только в детальном представлении)
- **`interactions`** (array) — Список недавних взаимодействий/сигналов (до 20 в детальном представлении)
  - Каждый элемент содержит:
    - `id` (integer) — ID взаимодействия
    - `created_at` (string) — ISO 8601 UTC datetime взаимодействия
    - `participant` (object) — Основной участник взаимодействия
      - `name` (string) — Имя участника (например, "Jack Zhang")
      - `slug` (string) — Slug участника (например, `jcz42`)
      - `type` (string) — Тип участника (например, "investor", "fund")
    - `associated_participant` (object|null) — Связанный участник (если применимо)
      - `name` (string) — Имя связанного участника (например, "Contrary")
      - `slug` (string) — Slug связанного участника (например, `contrary`)
      - `type` (string) — Тип участника (например, "fund")
- **`has_more_interactions`** (boolean) — Есть ли более 20 взаимодействий (используйте эндпоинт `/cards/<slug>/interactions/` для получения всех)

### Атрибуты участника

#### Базовые поля

- **`slug`** (string, обязательно) — URL-дружественный идентификатор, используемый в запросах API (например, `a16z`, `jcz42`)
- **`name`** (string, обязательно) — Имя участника (фонд, инвестор или имя человека)
- **`alt_name`** (string|null) — Альтернативное/дополнительное имя (например, "VC" для фонда)
- **`email`** (string|null) — Контактный email адрес
- **`image`** (string|null) — Абсолютный URL изображения/логотипа участника
- **`about`** (string|null) — Описание участника

#### Тип

- **`type`** (string, обязательно) — Идентификатор типа участника
  - Возможные значения: `fund`, `investor`, `angel`, `founder`, `accelerator` и т.д.
  - Получить доступные типы [здесь](#типы-участников)

#### Метрики

- **`monthly_signals`** (integer, обязательно) — Количество сигналов/взаимодействий в месяц

#### Связи

- **`associated_with`** (object|null) — Родительская организация (если участник связан с фондом)
  - `slug` (string) — Slug родительской организации (например, `a16z`)
  - `name` (string) — Название родительской организации (например, "a16z")
- **`self_associated`** (boolean, обязательно) — Связан ли участник сам с собой (часто для фондов, например, `true` для a16z)

#### Пользовательские данные (когда `include_user_data=true`)

- **`is_saved`** (boolean, опционально) — Сохранил ли пользователь этого участника

#### Дополнительные поля детального представления

- **`sources`** (array) — Список ссылок на социальные сети/источники
  - Каждый элемент содержит:
    - `slug` (string) — Идентификатор источника (например, `a16z`)
    - `type` (string) — Тип источника (например, "twitter", "linkedin-company", "linkedin")
    - `link` (string) — Полный URL профиля источника (например, `https://x.com/a16z`)

### Атрибуты взаимодействия

- **`id`** (integer, обязательно) — Уникальный ID взаимодействия/сигнала
- **`created_at`** (string, обязательно) — ISO 8601 UTC datetime когда произошло взаимодействие
- **`participant`** (object, обязательно) — Основной участник взаимодействия
  - `name` (string) — Имя участника
  - `slug` (string) — Slug участника
  - `type` (string) — Тип участника
- **`associated_participant`** (object|null) — Связанный участник (например, индивидуальный инвестор, связанный с фондом)
  - `name` (string) — Имя связанного участника
  - `slug` (string) — Slug связанного участника
  - `type` (string) — Тип участника

### Атрибуты пагинации

- **`limit`** (integer) — Количество записей на странице
- **`offset`** (integer) — Смещение от начала списка
- **`total`** (integer) — Общее количество доступных записей
- **`has_next`** (boolean) — Есть ли еще доступные записи

---

## Примечания

### Обработка ошибок

Все ошибки возвращаются в формате JSON:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {}
}
```

#### Основные коды ошибок

- `401 Unauthorized` — требуется аутентификация или недействительный токен
- `404 Not Found` — ресурс не найден
- `400 Bad Request` — ошибка валидации данных
- `429 Too Many Requests` — превышен лимит запросов
- `500 Internal Server Error` — внутренняя ошибка сервера

#### Примеры ответов с ошибками

**Недействительный токен (401 Unauthorized):**
```json
{
  "error": "authentication_failed",
  "message": "Invalid token or token not provided",
  "details": {}
}
```

**Ресурс не найден (404 Not Found):**
```json
{
  "error": "not_found",
  "message": "Resource not found",
  "details": {}
}
```

**Ошибка валидации данных (400 Bad Request):**
```json
{
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": {
    "limit": ["Ensure this value is less than or equal to 100."]
  }
}
```

**Превышен лимит запросов (429) - Платный доступ:**
```json
{
  "error": "throttled",
  "message": "Daily request limit exceeded. Limit: 500 requests per day.",
  "details": {
    "limit": 500,
    "wait_seconds": 3600
  }
}
```

**Превышен лимит запросов (429) - Бесплатный доступ:**
```json
{
  "error": "throttled",
  "message": "Total request limit exceeded. Limit: 100 requests total.",
  "details": {
    "limit": 100
  }
}
```

### Формат ответа

Все успешные ответы содержат поле `data` с данными и опциональное поле `pagination` для списков:

```json
{
  "data": [...],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "has_next": true
  }
}
```

### Форматы дат

**Параметры запроса (фильтры по датам):** Используйте формат `YYYY-MM-DD` (например, `2025-01-15`)
- Применяется к: `created_after`, `created_before`, `updated_after`, `updated_before`, `last_interaction_after`, `last_interaction_before`, `first_interaction_after`, `first_interaction_before`

**Поля ответа (дата-время):** Используйте формат ISO 8601 UTC с временем (например, `2025-01-15T10:30:00Z`)
- Применяется к: `created_at`, `updated_at`, `last_interaction_at`, `first_interaction_at` и всем полям datetime в ответах

**Исключение:** Поле `last_round` в ответах использует формат `YYYY-MM-DD` (только дата, например, `2025-01-15`)

---

## Ограничения и лимиты

### Лимиты запросов

API использует систему ограничения частоты запросов (rate limiting):

- **Бесплатный доступ:** 100 запросов всего (общий лимит)
- **Платный доступ:** 500 запросов в день (дневной лимит)

При превышении лимита возвращается ошибка `429 Too Many Requests` с информацией о времени ожидания (для платного доступа).

### Лимиты параметров

- **`limit`** для списка карточек: максимум 100 записей на страницу
- **`limit`** для списка взаимодействий: максимум 200 записей на страницу
- **`limit`** для списка участников: максимум 200 записей на страницу
- **`slugs`** для пакетного получения участников: максимум 100 slugs

### Версионирование

Текущая версия API: **v1**

Все эндпоинты находятся под префиксом `/v1/`. При изменении API будет выпущена новая версия с сохранением обратной совместимости для существующих версий.

---

## Примеры использования

### Получение списка популярных карточек

```http
GET /v1/cards/?limit=20&sort=trending&categories=ai,saas
Authorization: Token <your_token>
```

### Поиск участников по типу

```http
GET /v1/participants/?type=fund&sort=most_active&limit=50
Authorization: Token <your_token>
```

### Получение детальной информации о карточке с пользовательскими данными

```http
GET /v1/cards/project-slug/?include_user_data=true
Authorization: Token <your_token>
```

### Пакетное получение участников

```http
GET /v1/participants/batch/?slugs=investor-fund,john-doe,another-fund
Authorization: Token <your_token>
```

### Использование POST для больших фильтров

```http
POST /v1/cards/
Content-Type: application/json
Authorization: Token <your_token>

{
  "limit": 50,
  "sort": "trending",
  "categories": ["ai", "saas", "b2b", "fintech"],
  "stages": ["seed", "series_a"],
  "created_after": "2024-01-01"
}
```

---

## Часто задаваемые вопросы

### Как получить токен доступа?

Токен доступа выдается администратором системы. Для получения токена обратитесь к администратору платформы.

### Можно ли использовать API без аутентификации?

Нет, все эндпоинты требуют аутентификации через токен в заголовке `Authorization`.

### Как работает фильтрация по категориям?

При указании родительской категории автоматически включаются все дочерние категории. Например, при фильтрации по категории `ai` будут возвращены карточки с категориями `ai`, `machine_learning`, `computer_vision` и другими дочерними категориями.

### В чем разница между `latest_signal_date` и `last_interaction_at`?

`latest_signal_date` — это внутреннее поле, используемое для сортировки. `last_interaction_at` — это поле в ответе API, которое содержит дату последнего взаимодействия в формате ISO 8601 UTC.

### Как работает сортировка `trending`?

Сортировка `trending` возвращает карточки с наибольшим количеством взаимодействий, которые также имеют недавние сигналы (в пределах последней недели). Карточки сортируются сначала по количеству взаимодействий (по убыванию), затем по дате последнего сигнала (по убыванию).

---

## Поддержка

При возникновении проблем или вопросов обратитесь к администратору API или в службу поддержки платформы.
