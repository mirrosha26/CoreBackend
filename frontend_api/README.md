# Документация Frontend API

Frontend API — RESTful интерфейс для веб-приложения, обеспечивающий полный функционал управления карточками проектов, пользователями, папками, фильтрами и настройками дайджеста.

**Базовый URL:** `http://localhost:8000/frontend_api/`

**Аутентификация:** JWT токены через заголовок `Authorization: Bearer <access_token>`

Большинство эндпоинтов требуют аутентификации. Для получения токенов используйте эндпоинты `/auth/login/` или `/auth/register/`.

---

## Аутентификация

### Регистрация

**POST** `/auth/register/`

Создание нового пользователя.

#### Параметры запроса

- `email` (string, обязательно) — email пользователя
- `password` (string, обязательно) — пароль пользователя
- `first_name` (string, опционально) — имя пользователя
- `user_type` (string, опционально) — тип пользователя

#### Пример запроса

```http
POST /auth/register/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "user_type": "investor"
}
```

#### Пример ответа

```json
{
  "success": true,
  "message": "Registration completed successfully. Please wait for account activation."
}
```

---

### Вход в систему

**POST** `/auth/login/`

Аутентификация пользователя и получение JWT токенов.

#### Параметры запроса

- `email` (string, обязательно) — email пользователя
- `password` (string, обязательно) — пароль пользователя

#### Пример запроса

```http
POST /auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

#### Пример ответа

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

### Обновление токена

**POST** `/auth/refresh/`

Обновление access токена с помощью refresh токена.

#### Параметры запроса

- `refresh` (string, обязательно) — refresh токен

#### Пример запроса

```http
POST /auth/refresh/
Content-Type: application/json

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### Пример ответа

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

### Проверка токена

**POST** `/auth/verify/`

Проверка валидности access токена.

#### Параметры запроса

- `token` (string, обязательно) — access токен для проверки

---

### Выход из системы

**POST** `/auth/logout/`

Добавление refresh токена в черный список.

#### Параметры запроса

- `refresh` (string, обязательно) — refresh токен для добавления в черный список

---

### Метаданные регистрации

**GET** `/auth/registration-meta/`

Получение метаданных для формы регистрации (например, доступные типы пользователей).

#### Пример ответа

```json
{
  "success": true,
  "data": {
    "user_types": [
      {"value": "investor", "label": "Investor"},
      {"value": "founder", "label": "Founder"}
    ]
  }
}
```

---

### Управление Client API токенами

#### Получить список токенов

**GET** `/auth/client-tokens/`

Получение списка всех активных Client API токенов пользователя с информацией о лимитах доступа.

#### Пример ответа

```json
{
  "success": true,
  "data": {
    "tokens": [
      {
        "id": 1,
        "name": "Production API",
        "token_prefix": "api_",
        "created_at": "2024-01-15T10:30:00Z",
        "last_used_at": "2024-01-20T14:22:00Z",
        "is_active": true
      }
    ],
    "tokens_count": 1,
    "tokens_available": 4,
    "max_tokens": 5
  },
  "access": {
    "type": "paid",
    "is_paid": true,
    "limit": 500,
    "current_count": 120,
    "remaining": 380,
    "is_group_access": false,
    "group": null,
    "note": null
  }
}
```

#### Создать токен

**POST** `/auth/client-tokens/create/`

Создание нового Client API токена.

#### Параметры запроса

- `name` (string, обязательно) — название токена для идентификации

#### Пример запроса

```http
POST /auth/client-tokens/create/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "Development API Token"
}
```

#### Пример ответа

```json
{
  "success": true,
  "data": {
    "id": 2,
    "name": "Development API Token",
    "token": "api_abc123def456...",
    "token_prefix": "api_",
    "created_at": "2024-01-21T09:15:00Z",
    "is_active": true,
    "warning": "Save this token now. You will not be able to see it again."
  },
  "message": "Token created successfully"
}
```

#### Удалить токен

**DELETE** `/auth/client-tokens/<token_id>/delete/`

Удаление Client API токена.

---

## Профиль пользователя

### Получить профиль

**GET** `/user/profile/`

Получение информации о текущем пользователе.

#### Пример ответа

```json
{
  "success": true,
  "data": {
    "user": {
      "id": 1,
      "username": "user@example-com",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "avatar": "https://app.example.com/media/avatars/user.jpg",
      "user_type": "investor"
    },
    "is_superuser": false
  }
}
```

---

### Обновить профиль

**POST** `/user/profile/update/`

Обновление информации профиля пользователя.

#### Параметры запроса

- `first_name` (string, опционально) — имя
- `last_name` (string, опционально) — фамилия
- `user_type` (string, опционально) — тип пользователя
- `avatar` (file, опционально) — файл аватара для загрузки
- `avatar` (null/string, опционально) — установить в `null` для удаления аватара

#### Пример запроса

```http
POST /user/profile/update/
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

first_name=John
last_name=Doe
avatar=<file>
```

---

### Изменить пароль

**POST** `/user/password/change/`

Изменение пароля пользователя.

#### Параметры запроса

- `current_password` (string, обязательно) — текущий пароль
- `new_password` (string, обязательно) — новый пароль

#### Пример запроса

```http
POST /user/password/change/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "current_password": "oldpassword123",
  "new_password": "newpassword456"
}
```

---

### Настройки дайджеста

#### Получить настройки

**GET** `/user/digest-settings/`

Получение настроек email дайджеста пользователя.

#### Пример ответа

```json
{
  "is_enabled": true,
  "digest_hour": 8,
  "timezone": "America/New_York",
  "additional_emails": ["team@example.com"],
  "custom_filters_enabled": true,
  "custom_investors_enabled": false,
  "custom_folders_enabled": true
}
```

#### Обновить настройки

**POST** `/user/digest-settings/`

Обновление настроек email дайджеста.

#### Параметры запроса

- `is_enabled` (boolean, опционально) — включить/выключить дайджест
- `digest_hour` (integer, опционально) — час отправки (0-23)
- `timezone` (string, опционально) — часовой пояс
- `additional_emails` (array, опционально) — дополнительные email адреса
- `custom_filters_enabled` (boolean, опционально) — использовать сохраненные фильтры
- `custom_investors_enabled` (boolean, опционально) — использовать сохраненных инвесторов
- `custom_folders_enabled` (boolean, опционально) — использовать папки
- `filters` (array, опционально) — массив объектов `{id, in_digest}` для фильтров
- `participants` (array, опционально) — массив объектов `{id, in_digest}` для участников
- `folders` (array, опционально) — массив объектов `{id, in_digest}` для папок

---

### Сохраненные фильтры для дайджеста

#### Получить фильтры

**GET** `/user/digest-settings/saved-filters/`

Получение списка сохраненных фильтров пользователя для настроек дайджеста.

#### Параметры запроса

- `page` (integer, опционально) — номер страницы (по умолчанию 1)

#### Пример ответа

```json
{
  "filters": [
    {
      "id": 1,
      "name": "AI Startups",
      "in_digest": true
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_count": 5,
    "has_next": false,
    "has_previous": false
  }
}
```

---

### Сохраненные участники для дайджеста

#### Получить участников

**GET** `/user/digest-settings/saved-participants/`

Получение списка сохраненных участников пользователя для настроек дайджеста.

#### Параметры запроса

- `page` (integer, опционально) — номер страницы (по умолчанию 1)

#### Пример ответа

```json
{
  "participants": [
    {
      "id": 10,
      "name": "Y Combinator",
      "type": "fund",
      "image": "https://app.example.com/media/participants/yc.jpg",
      "about": "Seed stage accelerator",
      "in_digest": true
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_count": 15,
    "has_next": false,
    "has_previous": false
  }
}
```

---

### Папки для дайджеста

#### Получить папки

**GET** `/user/digest-settings/folders/`

Получение списка папок пользователя для настроек дайджеста.

#### Параметры запроса

- `page` (integer, опционально) — номер страницы (по умолчанию 1)

---

### Статус онбординга

#### Получить статус

**GET** `/user/onboarding/`

Получение статуса онбординга пользователя.

#### Пример ответа

```json
{
  "status": "IN_PROGRESS",
  "last_step_key": "step_3",
  "completed_at": null,
  "updated_at": "2024-01-15T10:30:00Z"
}
```

#### Обновить статус

**POST** `/user/onboarding/`

Обновление статуса онбординга.

#### Параметры запроса

- `status` (string, опционально) — статус: `IN_PROGRESS`, `COMPLETED`, `SKIPPED`, `DISABLED`
- `last_step_key` (string, опционально) — ключ последнего шага

---

### Обновление группы

**POST** `/user/group/update/`

Обновление информации о группе пользователя (имя и логотип).

#### Параметры запроса

- `name` (string, опционально) — новое имя группы
- `logo` (file, опционально) — файл логотипа для загрузки
- `logo` (null/string, опционально) — установить в `null` для удаления логотипа

---

## Карточки

### Получить список карточек

**GET** `/cards/`

Получение списка карточек с поддержкой фильтрации, поиска и пагинации.

#### Параметры запроса

- `page` (integer, опционально) — номер страницы (по умолчанию 1)
- `page_size` (integer, опционально) — количество записей на странице (по умолчанию 20)
- `search` (string, опционально) — поисковый запрос
- `type` (string, опционально) — тип списка: `notes` (заметки), `remote` (удаленные)
- `folder_key` (string, опционально) — ключ папки (`default` для избранного или ID папки)

#### Пример запроса

```http
GET /cards/?page=1&page_size=20&search=AI&type=notes
Authorization: Bearer <access_token>
```

#### Пример ответа

```json
{
  "success": true,
  "loadMore": true,
  "cards": [
    {
      "id": 1,
      "slug": "project-slug",
      "name": "Project Name",
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
      "is_favorite": true,
      "has_note": false,
      "note_text": null,
      "folders": [1, 2],
      "interactions_count": 15,
      "latest_signal_date": "2024-01-20T10:30:00Z"
    }
  ],
  "total_count": 150,
  "total_pages": 8,
  "current_page": 1
}
```

---

### Получить детали карточки

**GET** `/cards/<card_id>/`

Получение детальной информации о карточке.

#### Параметры запроса

- `card_id` (integer) — ID карточки в URL

#### Пример ответа

```json
{
  "success": true,
  "card": {
    "id": 1,
    "slug": "project-slug",
    "name": "Project Name",
    "description": "Full project description",
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
    "categories": [...],
    "signals": [...],
    "is_favorite": true,
    "has_note": true,
    "note_text": "My note about this project",
    "folders": [1, 2]
  }
}
```

---

### Добавить/удалить из избранного

**POST** `/cards/<card_id>/favorite/`

Добавление карточки в избранное (папку по умолчанию).

**DELETE** `/cards/<card_id>/favorite/`

Удаление карточки из избранного.

#### Пример ответа

```json
{
  "success": true,
  "message": "Карточка успешно добавлена в избранное"
}
```

---

### Удалить/восстановить карточку

**POST** `/cards/<card_id>/delete/`

Добавление карточки в список удаленных.

**DELETE** `/cards/<card_id>/delete/`

Восстановление карточки из списка удаленных.

---

### Управление заметками

#### Получить заметку

**GET** `/cards/<card_id>/note/`

Получение заметки к карточке.

#### Пример ответа

```json
{
  "success": true,
  "note": {
    "card_id": 1,
    "note_text": "This is my note",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T14:22:00Z"
  }
}
```

#### Создать/обновить заметку

**POST** `/cards/<card_id>/note/`

Создание или обновление заметки к карточке.

#### Параметры запроса

- `note_text` (string, обязательно) — текст заметки (пустая строка для удаления)

#### Пример запроса

```http
POST /cards/1/note/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "note_text": "This is my updated note"
}
```

#### Удалить заметку

**DELETE** `/cards/<card_id>/note/`

Удаление заметки к карточке.

---

### Управление папками карточки

#### Получить папки карточки

**GET** `/cards/<card_id>/folders/`

Получение списка всех папок пользователя с указанием, в каких находится данная карточка.

#### Пример ответа

```json
{
  "success": true,
  "folders": [
    {
      "id": 1,
      "name": "Favorites",
      "is_default": true,
      "has_card": true
    },
    {
      "id": 2,
      "name": "AI Projects",
      "is_default": false,
      "has_card": false
    }
  ]
}
```

#### Обновить папки карточки

**POST** `/cards/<card_id>/folders/`

Обновление списка папок, в которых находится карточка.

#### Параметры запроса

- `include_folders` (array, опционально) — массив ID папок, в которые нужно добавить карточку
- `exclude_folders` (array, опционально) — массив ID папок, из которых нужно удалить карточку

#### Пример запроса

```http
POST /cards/1/folders/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "include_folders": [2, 3],
  "exclude_folders": [1]
}
```

---

### Участники группы по карточке

#### Получить участников группы

**GET** `/cards/<card_id>/group-members/`

Получение списка участников группы пользователя с информацией о назначениях на карточку.

#### Пример ответа

```json
{
  "success": true,
  "group": {
    "id": 1,
    "name": "My Team",
    "slug": "my-team"
  },
  "card_id": 1,
  "card_name": "Project Name",
  "status": "REVIEW",
  "members": [
    {
      "id": 10,
      "username": "john@example-com",
      "first_name": "John",
      "last_name": "Doe",
      "avatar": "https://app.example.com/media/avatars/john.jpg",
      "is_assigned": true,
      "assigned_by": {
        "id": 11,
        "username": "jane@example-com",
        "first_name": "Jane",
        "last_name": "Smith",
        "avatar": "https://app.example.com/media/avatars/jane.jpg"
      },
      "assigned_at": "2024-01-20T10:30:00Z"
    }
  ],
  "has_group_assignment": true
}
```

#### Назначить карточку группе

**POST** `/cards/<card_id>/group-members/`

Назначение карточки группе и/или участников группы на карточку.

#### Параметры запроса

- `member_ids` (array, опционально) — список ID участников для назначения
- `status` (string, опционально) — начальный статус карточки (по умолчанию `REVIEW`)
- `action` (string, опционально) — действие: `replace` (заменить), `add` (добавить), `remove` (удалить)

#### Пример запроса

```http
POST /cards/1/group-members/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "member_ids": [10, 11],
  "status": "REVIEW",
  "action": "replace"
}
```

#### Обновить назначение

**PATCH** `/cards/<card_id>/group-members/`

Изменение статуса назначения карточки группе и/или управление назначениями участников.

#### Параметры запроса

- `status` (string, опционально) — новый статус карточки
- `member_ids` (array, опционально) — список ID участников (пустой массив для снятия всех назначений)
- `action` (string, опционально) — действие: `replace`, `add`, `remove`

---

## Публичные карточки

### Получить preview карточки

**GET** `/public/<identifier>/preview/`

Получение preview информации о публичной карточке без авторизации.

#### Параметры запроса

- `identifier` (string) — UUID или slug карточки в URL

#### Пример запроса

```http
GET /public/550e8400-e29b-41d4-a716-446655440000/preview/
```

---

### Получить детали публичной карточки

**GET** `/public/<identifier>/detail/`

Получение детальной информации о публичной карточке.

#### Параметры запроса

- `identifier` (string) — UUID или slug карточки в URL
- `include_signals` (boolean, опционально) — включать сигналы (по умолчанию `true`)
- `signals_limit` (integer, опционально) — лимит сигналов (по умолчанию 5)

#### Пример запроса

```http
GET /public/project-slug/detail/?include_signals=true&signals_limit=10
```

---

## Папки

### Получить список папок

**GET** `/folders/`

Получение списка всех папок пользователя.

#### Пример ответа

```json
{
  "success": true,
  "folders": [
    {
      "id": 1,
      "name": "Favorites",
      "description": "My favorite projects",
      "is_default": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:22:00Z",
      "cards_count": 25,
      "folder_key": "default"
    },
    {
      "id": 2,
      "name": "AI Projects",
      "description": "",
      "is_default": false,
      "created_at": "2024-01-16T09:15:00Z",
      "updated_at": "2024-01-16T09:15:00Z",
      "cards_count": 10,
      "folder_key": "2"
    }
  ]
}
```

---

### Создать папку

**POST** `/folders/`

Создание новой папки.

#### Параметры запроса

- `name` (string, обязательно) — название папки
- `description` (string, опционально) — описание папки
- `is_default` (boolean, опционально) — является ли папкой по умолчанию

#### Пример запроса

```http
POST /folders/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "My New Folder",
  "description": "Description of the folder"
}
```

---

### Получить детали папки

**GET** `/folders/<folder_id>/`

Получение информации о конкретной папке.

---

### Обновить папку

**PUT** `/folders/<folder_id>/`

Обновление информации о папке.

#### Параметры запроса

- `name` (string, обязательно) — новое название папки
- `description` (string, опционально) — новое описание папки

---

### Удалить папку

**DELETE** `/folders/<folder_id>/`

Удаление папки. Папку по умолчанию удалить нельзя.

---

### Экспорт папки

**GET** `/folders/export/`

Экспорт всех карточек из папки в CSV файл.

#### Параметры запроса

- `folder` (string, обязательно) — ID папки или `favorites` для папки по умолчанию

#### Пример запроса

```http
GET /folders/export/?folder=favorites
Authorization: Bearer <access_token>
```

Ответ будет содержать CSV файл с данными о карточках.

---

## Ленты

### Все сигналы

**GET** `/feeds/all-signals/`

Получение ленты всех сигналов с фильтрацией.

#### Параметры запроса

- `page` (integer, опционально) — номер страницы (по умолчанию 1)
- `page_size` (integer, опционально) — количество записей на странице (по умолчанию 20)
- `search` (string, опционально) — поисковый запрос
- `last_week` (boolean, опционально) — показывать только за последнюю неделю
- `start_date` (string, опционально) — начальная дата (формат: `ДД.ММ.ГГГГ`)
- `end_date` (string, опционально) — конечная дата (формат: `ДД.ММ.ГГГГ`)
- `hide_liked` (boolean, опционально) — скрыть избранные карточки
- `min_sig` (integer, опционально) — минимальное количество сигналов (по умолчанию 1)
- `max_sig` (integer, опционально) — максимальное количество сигналов

#### Пример запроса

```http
GET /feeds/all-signals/?page=1&page_size=20&search=AI&last_week=true
Authorization: Bearer <access_token>
```

#### Пример ответа

```json
{
  "success": true,
  "loadMore": true,
  "cards": [...],
  "total_count": 150,
  "total_pages": 8,
  "current_page": 1
}
```

---

### Персональная лента

**GET** `/feeds/personal/`

Получение персональной ленты пользователя на основе сохраненных участников и настроек UserFeed.

#### Параметры запроса

Те же, что и для `/feeds/all-signals/`

---

## Фильтры

### Фильтры для всех сигналов

#### Получить доступные фильтры

**GET** `/filters/all-signals/`

Получение доступных опций фильтрации для ленты всех сигналов.

#### Параметры запроса

- `category` (array, опционально) — массив slug категорий для фильтрации
- `stage` (array, опционально) — массив slug стадий для фильтрации
- `round` (array, опционально) — массив slug раундов для фильтрации
- `participant` (array, опционально) — массив slug участников для фильтрации

#### Пример ответа

```json
{
  "success": true,
  "stages": [
    {"slug": "seed", "name": "Seed", "active": true},
    {"slug": "series_a", "name": "Series A", "active": false}
  ],
  "rounds": [
    {"slug": "raising_now", "name": "Raising Now", "active": false}
  ],
  "participants": [
    {
      "name": "Y Combinator",
      "image": "https://app.example.com/media/participants/yc.jpg",
      "slug": "y-combinator",
      "active": true
    }
  ],
  "categories": [
    {"name": "SaaS", "slug": "saas", "active": false},
    {"name": "AI", "slug": "ai", "active": true}
  ]
}
```

#### Сохранить фильтры в сессию

**POST** `/filters/all-signals/`

Сохранение фильтров в сессию пользователя.

#### Параметры запроса

- `categories` (array, опционально) — массив slug категорий
- `stages` (array, опционально) — массив slug стадий
- `rounds` (array, опционально) — массив slug раундов
- `participants` (array, опционально) — массив slug участников

---

### Фильтры для персональной ленты

#### Получить доступные фильтры

**GET** `/filters/personal/`

Получение доступных опций фильтрации для персональной ленты.

#### Параметры запроса

Те же, что и для `/filters/all-signals/`

#### Обновить настройки ленты

**POST** `/filters/personal/`

Обновление настроек персональной ленты (UserFeed).

#### Параметры запроса

- `categories` (array, опционально) — массив slug категорий
- `stages` (array, опционально) — массив slug стадий
- `rounds` (array, опционально) — массив slug раундов
- `participants` (array, опционально) — массив slug участников

---

## Инвесторы

### Получить список инвесторов

**GET** `/investors/`

Получение списка инвесторов/участников.

#### Параметры запроса

- `filter_saved` (string, опционально) — фильтр: `true` (только сохраненные), `false` (только несохраненные)

#### Пример ответа

```json
{
  "success": true,
  "data": [
    {
      "id": 10,
      "name": "Y Combinator",
      "slug": "y-combinator",
      "type": "fund",
      "is_saved": true,
      "image": "https://app.example.com/media/participants/yc.jpg",
      "num_cards": 45
    }
  ]
}
```

---

## Тикеты

### Создать запрос на контакт

**POST** `/tickets/`

Создание запроса на контакт с проектом.

#### Параметры запроса

- `card_id` (integer, обязательно) — ID карточки проекта

#### Пример запроса

```http
POST /tickets/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "card_id": 1
}
```

#### Пример ответа

```json
{
  "success": true,
  "message": "Contact request sent successfully."
}
```

---

### Получить список тикетов

**GET** `/tickets/`

Получение списка всех тикетов пользователя.

#### Пример ответа

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "signal_card_name": "Project Name",
      "signal_card_image": "https://app.example.com/media/...",
      "is_processed": false,
      "created_at": "2024-01-15T10:30:00Z",
      "response_text": null
    }
  ]
}
```

---

### Удалить тикет

**DELETE** `/tickets/`

Удаление тикета.

#### Параметры запроса

- `ticket_id` (integer, обязательно) — ID тикета

---

## Сохраненные фильтры

### Получить список фильтров

**GET** `/saved-filters/`

Получение списка всех сохраненных фильтров пользователя.

#### Параметры запроса

- `detailed` (boolean, опционально) — возвращать полную информацию о фильтрах
- `include_default` (boolean, опционально) — включать информацию о фильтре по умолчанию

#### Пример ответа

```json
{
  "success": true,
  "count": 3,
  "filters": [
    {
      "id": 1,
      "name": "AI Startups",
      "is_default": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:22:00Z"
    }
  ],
  "default_filter_id": 1
}
```

---

### Создать фильтр

**POST** `/saved-filters/`

Создание нового сохраненного фильтра.

#### Параметры запроса

- `name` (string, обязательно) — название фильтра
- `search` (string, опционально) — поисковый запрос
- `categories` (array, опционально) — массив ID категорий
- `participants` (array, опционально) — массив ID участников
- `stages` (array, опционально) — массив slug стадий
- `round_statuses` (array, опционально) — массив slug раундов
- `featured` (boolean, опционально) — только избранные
- `is_open` (boolean, опционально) — только открытые
- `start_date` (string, опционально) — начальная дата
- `end_date` (string, опционально) — конечная дата
- `min_signals` (integer, опционально) — минимальное количество сигналов
- `max_signals` (integer, опционально) — максимальное количество сигналов
- `hide_liked` (boolean, опционально) — скрыть избранные

---

### Получить детали фильтра

**GET** `/saved-filters/<filter_id>/`

Получение детальной информации о сохраненном фильтре.

---

### Обновить фильтр

**PUT** `/saved-filters/<filter_id>/`

Полное обновление сохраненного фильтра.

**PATCH** `/saved-filters/<filter_id>/`

Частичное обновление сохраненного фильтра.

---

### Удалить фильтр

**DELETE** `/saved-filters/<filter_id>/`

Удаление сохраненного фильтра.

---

### Применить фильтр

**POST** `/saved-filters/<filter_id>/apply/`

Применение сохраненного фильтра к текущим настройкам фильтрации (сохранение в сессию).

---

### Установить фильтр по умолчанию

**POST** `/saved-filters/<filter_id>/set-default/`

Установка сохраненного фильтра как фильтра по умолчанию.

**DELETE** `/saved-filters/<filter_id>/set-default/`

Снятие статуса фильтра по умолчанию.

---

## Коды ошибок

### Общие ошибки

- `MISSING_FIELDS` — не указаны обязательные поля
- `INVALID_EMAIL` — неверный формат email
- `USER_NOT_FOUND` — пользователь не найден
- `INVALID_CREDENTIALS` — неверные учетные данные
- `USER_INACTIVE` — учетная запись не активирована
- `SERVER_ERROR` — внутренняя ошибка сервера
- `NOT_AUTHENTICATED` — пользователь не аутентифицирован
- `ACCESS_DENIED` — доступ запрещен
- `NOT_FOUND` — ресурс не найден

### Ошибки карточек

- `MISSING_CARD_ID` — не указан ID карточки
- `ALREADY_LIKED` — карточка уже в избранном
- `NOT_LIKED` — карточка не найдена в избранном
- `ALREADY_DELETED` — карточка уже удалена
- `NOT_DELETED` — карточка не найдена в списке удаленных
- `NOTE_NOT_FOUND` — заметка не найдена
- `MISSING_NOTE_TEXT` — не указан текст заметки

### Ошибки папок

- `MISSING_NAME` — не указано название папки
- `FOLDER_NOT_FOUND` — папка не найдена
- `DEFAULT_FOLDER` — нельзя удалить папку по умолчанию
- `DUPLICATE_NAME` — папка с таким названием уже существует

### Ошибки токенов

- `MISSING_NAME` — не указано название токена
- `TOKEN_LIMIT_EXCEEDED` — превышен лимит токенов (максимум 5)
- `TOKEN_NOT_FOUND` — токен не найден
- `MISSING_TOKEN_ID` — не указан ID токена

### Ошибки групп

- `NO_GROUP` — пользователь не состоит в группе
- `NOT_ASSIGNED` — карточка не назначена группе
- `INVALID_STATUS` — недопустимый статус
- `INVALID_MEMBERS` — указанные участники не принадлежат группе
- `INVALID_NAME` — неверное имя группы

---

## Примечания

1. **Аутентификация**: Большинство эндпоинтов требуют JWT токен в заголовке `Authorization: Bearer <access_token>`.

2. **Пагинация**: Эндпоинты, возвращающие списки, поддерживают пагинацию через параметры `page` и `page_size`.

3. **Фильтрация**: Многие эндпоинты поддерживают фильтрацию через query параметры или сохраненные фильтры в сессии.

4. **Избранное**: Избранное реализовано через папку по умолчанию (`is_default=True`). Используйте `folder_key=default` для работы с избранным.

5. **Группы**: Функционал групп позволяет назначать карточки участникам группы и отслеживать статусы работы с карточками.

6. **Публичные карточки**: Публичные эндпоинты (`/public/`) не требуют аутентификации, но работают только с карточками, у которых `is_open=True`.

7. **Экспорт**: Экспорт папок доступен в формате CSV через эндпоинт `/folders/export/`.

8. **Дайджест**: Настройки email дайджеста позволяют настраивать автоматическую отправку подборок проектов на основе сохраненных фильтров, участников и папок.
