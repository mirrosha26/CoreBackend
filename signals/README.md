# Signals - Серверное API

## 📋 Содержание

1. [Обзор](#обзор)
2. [Аутентификация](#аутентификация)
3. [Базовый URL](#базовый-url)
4. [Endpoints](#endpoints)
   - [Получение токена](#1-получение-токена)
   - [Stages и Rounds](#2-stages-и-rounds)
   - [Source Types](#3-source-types-типы-источников)
   - [Signal Types](#4-signal-types-типы-сигналов)
   - [Sources](#5-sources-источники)
   - [Categories](#6-categories-категории)
   - [Participants](#7-participants-участники)
   - [Signal Cards](#8-signal-cards-проекты)
   - [Team Members](#9-team-members-члены-команды)
   - [Signals](#10-signals-сигналы)
5. [Фильтрация и поиск](#фильтрация-и-поиск)
6. [Пагинация](#пагинация)
7. [Коды ответов](#коды-ответов)
8. [Примеры использования](#примеры-использования)

---

## Обзор

Signals API — это серверное RESTful API для управления сигналами венчурного финансирования, проектами, участниками (фондами, инвесторами), источниками данных и связанными сущностями.

**Основные возможности:**
- ✅ CRUD операции для основных моделей
- ✅ Фильтрация, поиск и сортировка данных
- ✅ Пагинация результатов
- ✅ Token-based аутентификация
- ✅ Детальная информация о связанных объектах

---

## Аутентификация

Все endpoints требуют аутентификации через Token Authentication.

### Формат заголовка:
```http
Authorization: Token <ваш_токен>
```

### Как получить токен:
См. раздел [Получение токена](#1-получение-токена)

---

## Базовый URL

```
http://localhost:8000/s-api/
```

Для production замените на актуальный домен.

---

## Endpoints

### 1. Получение токена

**Эндпоинт для получения токена аутентификации.**

#### `POST /s-api/token-auth/`

**Request:**
```http
POST /s-api/token-auth/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response (200 OK):**
```json
{
  "token": "deb048787607e4ecd39b36f513e724adc594bd41"
}
```

**Пример использования токена:**
```http
GET /s-api/stages/
Authorization: Token deb048787607e4ecd39b36f513e724adc594bd41
```

**Ошибки:**
- `400 Bad Request` - Неверные учетные данные
- `400 Bad Request` - Отсутствуют обязательные поля

---

### 2. Stages и Rounds

**Справочные endpoints для получения списков стадий и раундов финансирования.**

#### `GET /s-api/stages/`

Получить список всех доступных стадий (seed, series-a, series-b и т.д.).

**Request:**
```http
GET /s-api/stages/
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
[
  {
    "value": "ideation",
    "label": "Ideation"
  },
  {
    "value": "seed",
    "label": "Seed"
  },
  {
    "value": "series-a",
    "label": "Series A"
  }
]
```

#### `GET /s-api/rounds/`

Получить список всех доступных раундов финансирования.

**Request:**
```http
GET /s-api/rounds/
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
[
  {
    "value": "pre-seed",
    "label": "Pre-Seed"
  },
  {
    "value": "seed",
    "label": "Seed"
  },
  {
    "value": "series-a",
    "label": "Series A"
  }
]
```

---

### 3. Source Types (Типы источников)

**Read-Only endpoint для типов источников данных.**

#### `GET /s-api/source-types/`

Получить список всех типов источников.

**Request:**
```http
GET /s-api/source-types/
Authorization: Token <your_token>
```

**Query Parameters:**
- `search` - Поиск по названию или slug
- `ordering` - Сортировка (id, name, -name)
- `page` - Номер страницы
- `page_size` - Количество записей на странице

**Пример с фильтрами:**
```http
GET /s-api/source-types/?search=twitter&ordering=name&page_size=20
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "twitter",
      "name": "Twitter",
      "description": "Twitter social network"
    },
    {
      "id": 2,
      "slug": "linkedin",
      "name": "LinkedIn",
      "description": "LinkedIn professional network"
    }
  ]
}
```

#### `GET /s-api/source-types/{id}/`

Получить конкретный тип источника по ID.

**Request:**
```http
GET /s-api/source-types/1/
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "id": 1,
  "slug": "twitter",
  "name": "Twitter",
  "description": "Twitter social network"
}
```

---

### 4. Signal Types (Типы сигналов)

**Read-Only endpoint для типов сигналов.**

#### `GET /s-api/signal-types/`

Получить список всех типов сигналов.

**Request:**
```http
GET /s-api/signal-types/
Authorization: Token <your_token>
```

**Query Parameters:**
- `search` - Поиск по названию или slug
- `ordering` - Сортировка
- `page`, `page_size` - Пагинация

**Response (200 OK):**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "investment",
      "name": "Investment",
      "description": "Investment signal"
    }
  ]
}
```

#### `GET /s-api/signal-types/{id}/`

Получить конкретный тип сигнала.

---

### 5. Sources (Источники)

**CRUD операции для источников данных из социальных сетей.**

#### `GET /s-api/sources/`

Получить список всех источников.

**Query Parameters:**
- `search` - Поиск по slug
- `source_type` - Фильтр по типу источника (ID)
- `participant` - Фильтр по участнику (ID)
- `ordering` - Сортировка

**Пример:**
```http
GET /s-api/sources/?source_type=1&participant=5
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 10,
  "next": "http://localhost:8000/s-api/sources/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "example_account",
      "source_type_id": 1,
      "participant_id": 5,
      "tracking_enabled": true,
      "blocked": false,
      "nonexistent": false,
      "social_network_id": "123456789"
    }
  ]
}
```

#### `POST /s-api/sources/`

Создать новый источник.

**Request:**
```http
POST /s-api/sources/
Authorization: Token <your_token>
Content-Type: application/json

{
  "slug": "new_account",
  "source_type_id": 2,
  "participant_id": 10,
  "tracking_enabled": true,
  "social_network_id": "987654321"
}
```

**Обязательные поля:**
- `slug` - Идентификатор профиля в соцсети
- `source_type_id` - ID типа источника

**Опциональные поля:**
- `participant_id` - ID участника
- `tracking_enabled` - Включено ли отслеживание (по умолчанию true)
- `blocked` - Заблокирован ли (по умолчанию false)
- `nonexistent` - Не существует ли (по умолчанию false)
- `social_network_id` - ID профиля в соцсети

**Response (201 Created):**
```json
{
  "id": 15,
  "slug": "new_account",
  "source_type_id": 2,
  "participant_id": 10,
  "tracking_enabled": true,
  "blocked": false,
  "nonexistent": false,
  "social_network_id": "987654321"
}
```

#### `GET /s-api/sources/{id}/`

Получить конкретный источник.

#### `PATCH /s-api/sources/{id}/`

Обновить источник.

**Request:**
```http
PATCH /s-api/sources/15/
Authorization: Token <your_token>
Content-Type: application/json

{
  "tracking_enabled": false
}
```

#### `DELETE /s-api/sources/{id}/`

Удалить источник.

**Response (204 No Content)**

---

### 6. Categories (Категории)

**CRUD операции для категорий проектов.**

#### `GET /s-api/categories/`

Получить список всех категорий.

**Query Parameters:**
- `search` - Поиск по имени или slug
- `ordering` - Сортировка

**Response (200 OK):**
```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "ai",
      "name": "AI & Machine Learning",
      "created_at": "2025-01-10T12:00:00Z",
      "updated_at": "2025-01-10T12:00:00Z"
    },
    {
      "id": 2,
      "slug": "fintech",
      "name": "FinTech",
      "created_at": "2025-01-10T12:05:00Z",
      "updated_at": "2025-01-10T12:05:00Z"
    }
  ]
}
```

#### `POST /s-api/categories/`

Создать новую категорию.

**Request:**
```http
POST /s-api/categories/
Authorization: Token <your_token>
Content-Type: application/json

{
  "slug": "defi",
  "name": "DeFi"
}
```

**Response (201 Created):**
```json
{
  "id": 9,
  "slug": "defi",
  "name": "DeFi",
  "created_at": "2025-12-30T16:00:00Z",
  "updated_at": "2025-12-30T16:00:00Z"
}
```

#### `GET /s-api/categories/{id}/`

Получить конкретную категорию.

#### `PATCH /s-api/categories/{id}/`

Обновить категорию.

#### `DELETE /s-api/categories/{id}/`

Удалить категорию.

---

### 7. Participants (Участники)

**CRUD операции для участников (фонды, инвесторы, компании).**

#### `GET /s-api/participants/`

Получить список всех участников.

**Query Parameters:**
- `search` - Поиск по имени или slug
- `participant_type` - Фильтр по типу (fund, angel_investor, corporate, accelerator)
- `ordering` - Сортировка

**Пример:**
```http
GET /s-api/participants/?participant_type=fund&ordering=name
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 25,
  "next": "http://localhost:8000/s-api/participants/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "sequoia-capital",
      "name": "Sequoia Capital",
      "participant_type": "fund",
      "logo": "https://example.com/media/logos/sequoia.png",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

#### `POST /s-api/participants/`

Создать нового участника.

**Request:**
```http
POST /s-api/participants/
Authorization: Token <your_token>
Content-Type: application/json

{
  "slug": "a16z",
  "name": "Andreessen Horowitz",
  "participant_type": "fund",
  "logo": "https://example.com/a16z-logo.png"
}
```

**Response (201 Created):**
```json
{
  "id": 26,
  "slug": "a16z",
  "name": "Andreessen Horowitz",
  "participant_type": "fund",
  "logo": "https://example.com/a16z-logo.png",
  "created_at": "2025-12-30T16:20:00Z",
  "updated_at": "2025-12-30T16:20:00Z"
}
```

#### `GET /s-api/participants/{id}/`

Получить конкретного участника.

#### `PATCH /s-api/participants/{id}/`

Обновить участника.

**Request:**
```http
PATCH /s-api/participants/26/
Authorization: Token <your_token>
Content-Type: application/json

{
  "logo": "https://example.com/new-a16z-logo.png"
}
```

#### `DELETE /s-api/participants/{id}/`

Удалить участника.

---

### 8. Signal Cards (Проекты)

**CRUD операции для карточек проектов (компаний).**

#### `GET /s-api/signal-cards/`

Получить список всех проектов.

**Query Parameters:**
- `search` - Поиск по имени, slug, описанию
- `stage` - Фильтр по стадии (seed, series-a и т.д.)
- `round` - Фильтр по раунду
- `category` - Фильтр по категории (ID)
- `is_open` - Фильтр по статусу открытости (true/false)
- `is_featured` - Фильтр по избранным (true/false)
- `ordering` - Сортировка (-created_at, name, -updated_at)

**Пример:**
```http
GET /s-api/signal-cards/?stage=seed&is_open=true&ordering=-created_at&page_size=10
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "http://localhost:8000/s-api/signal-cards/?page=2&stage=seed",
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "awesome-startup",
      "name": "Awesome Startup",
      "description": "Revolutionary AI platform",
      "stage": "seed",
      "round": "seed",
      "logo": "https://example.com/logos/awesome.png",
      "website": "https://awesome-startup.com",
      "is_open": true,
      "is_featured": false,
      "category": 1,
      "created_at": "2025-12-01T10:00:00Z",
      "updated_at": "2025-12-30T14:20:00Z"
    }
  ]
}
```

#### `POST /s-api/signal-cards/`

Создать новый проект.

**Request:**
```http
POST /s-api/signal-cards/
Authorization: Token <your_token>
Content-Type: application/json

{
  "slug": "new-project",
  "name": "New Project",
  "description": "Amazing new project description",
  "stage": "ideation",
  "round": "pre-seed",
  "website": "https://new-project.com",
  "is_open": true,
  "category": 2
}
```

**Response (201 Created):**
```json
{
  "id": 51,
  "slug": "new-project",
  "name": "New Project",
  "description": "Amazing new project description",
  "stage": "ideation",
  "round": "pre-seed",
  "logo": null,
  "website": "https://new-project.com",
  "is_open": true,
  "is_featured": false,
  "category": 2,
  "created_at": "2025-12-30T16:30:00Z",
  "updated_at": "2025-12-30T16:30:00Z"
}
```

#### `GET /s-api/signal-cards/{id}/`

Получить конкретный проект.

**Response (200 OK):**
```json
{
  "id": 1,
  "slug": "awesome-startup",
  "name": "Awesome Startup",
  "description": "Revolutionary AI platform for...",
  "stage": "seed",
  "round": "seed",
  "logo": "https://example.com/logos/awesome.png",
  "website": "https://awesome-startup.com",
  "is_open": true,
  "is_featured": false,
  "category": 1,
  "created_at": "2025-12-01T10:00:00Z",
  "updated_at": "2025-12-30T14:20:00Z"
}
```

#### `PATCH /s-api/signal-cards/{id}/`

Обновить проект.

**Request:**
```http
PATCH /s-api/signal-cards/51/
Authorization: Token <your_token>
Content-Type: application/json

{
  "stage": "seed",
  "is_featured": true
}
```

#### `DELETE /s-api/signal-cards/{id}/`

Удалить проект.

---

### 9. Team Members (Члены команды)

**CRUD операции для членов команд проектов.**

#### `GET /s-api/team-members/`

Получить список всех членов команд.

**Query Parameters:**
- `search` - Поиск по имени
- `signal_card` - Фильтр по проекту (ID)
- `ordering` - Сортировка

**Пример:**
```http
GET /s-api/team-members/?signal_card=1
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "John Smith",
      "role": "CEO",
      "signal_card": 1,
      "created_at": "2025-12-01T10:05:00Z",
      "updated_at": "2025-12-01T10:05:00Z"
    },
    {
      "id": 2,
      "name": "Jane Doe",
      "role": "CTO",
      "signal_card": 1,
      "created_at": "2025-12-01T10:06:00Z",
      "updated_at": "2025-12-01T10:06:00Z"
    }
  ]
}
```

#### `POST /s-api/team-members/`

Добавить члена команды.

**Request:**
```http
POST /s-api/team-members/
Authorization: Token <your_token>
Content-Type: application/json

{
  "name": "Alice Johnson",
  "role": "CFO",
  "signal_card": 51
}
```

**Response (201 Created):**
```json
{
  "id": 25,
  "name": "Alice Johnson",
  "role": "CFO",
  "signal_card": 51,
  "created_at": "2025-12-30T16:40:00Z",
  "updated_at": "2025-12-30T16:40:00Z"
}
```

#### `GET /s-api/team-members/{id}/`

Получить конкретного члена команды.

#### `PATCH /s-api/team-members/{id}/`

Обновить члена команды.

#### `DELETE /s-api/team-members/{id}/`

Удалить члена команды.

---

### 10. Signals (Сигналы)

**CRUD операции для сигналов интереса.**

Сигналы представляют интерес участника к проекту (например, инвестиция, партнерство).

#### `GET /s-api/signals/`

Получить список всех сигналов.

**Query Parameters:**
- `search` - Поиск
- `signal_type` - Фильтр по типу сигнала (ID)
- `signal_card` - Фильтр по проекту (ID)
- `participant` - Фильтр по участнику (ID)
- `associated_participant` - Фильтр по связанному участнику (ID)
- `source` - Фильтр по источнику (ID)
- `date_after` - Фильтр по дате (после)
- `date_before` - Фильтр по дате (до)
- `ordering` - Сортировка

**Пример:**
```http
GET /s-api/signals/?signal_card=1&date_after=2025-01-01&ordering=-date
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "signal_type": 1,
      "signal_card": 1,
      "participant": 5,
      "associated_participant": 10,
      "source": 3,
      "date": "2025-12-15",
      "amount": "1000000.00",
      "privacy": "public",
      "created_at": "2025-12-15T11:00:00Z",
      "updated_at": "2025-12-15T11:00:00Z"
    }
  ]
}
```

#### `POST /s-api/signals/`

Создать новый сигнал.

**Request:**
```http
POST /s-api/signals/
Authorization: Token <your_token>
Content-Type: application/json

{
  "signal_type": 1,
  "signal_card": 51,
  "participant": 26,
  "date": "2025-12-30",
  "amount": "500000.00",
  "privacy": "public"
}
```

**Обязательные поля:**
- `signal_type` - Тип сигнала (ID)
- `signal_card` - Проект (ID)
- `participant` - Участник (ID)
- `date` - Дата сигнала (YYYY-MM-DD)

**Опциональные поля:**
- `associated_participant` - Связанный участник (ID)
- `source` - Источник данных (ID)
- `amount` - Сумма (decimal)
- `privacy` - Приватность (public, private)

**Response (201 Created):**
```json
{
  "id": 13,
  "signal_type": 1,
  "signal_card": 51,
  "participant": 26,
  "associated_participant": null,
  "source": null,
  "date": "2025-12-30",
  "amount": "500000.00",
  "privacy": "public",
  "created_at": "2025-12-30T16:50:00Z",
  "updated_at": "2025-12-30T16:50:00Z"
}
```

#### `GET /s-api/signals/{id}/`

Получить конкретный сигнал.

#### `PATCH /s-api/signals/{id}/`

Обновить сигнал.

**Request:**
```http
PATCH /s-api/signals/13/
Authorization: Token <your_token>
Content-Type: application/json

{
  "amount": "750000.00",
  "privacy": "private"
}
```

#### `DELETE /s-api/signals/{id}/`

Удалить сигнал.

---

### 11. SignalRaw (Сырые данные сигналов)

**CRUD операции для сырых данных от микросервиса сбора данных.**

Модель для хранения необработанных данных о сигналах до их проверки и преобразования в полноценные Signal и SignalCard записи.

#### `GET /s-api/signals-raw/`

Получить список всех сырых сигналов.

**Query Parameters:**
- `is_processed` - Фильтр по статусу обработки (true/false)
- `source` - Фильтр по источнику (ID)
- `signal_type` - Фильтр по типу сигнала (ID)
- `category` - Фильтр по категории
- `stage` - Фильтр по стадии
- `round` - Фильтр по раунду
- `search` - Полнотекстовый поиск
- `ordering` - Сортировка
- `page`, `page_size` - Пагинация

**Примеры:**

```http
# Все необработанные сигналы
GET /s-api/signals-raw/?is_processed=false
Authorization: Token <your_token>
```

```http
# По стадии и категории
GET /s-api/signals-raw/?stage=seed&category=ai
Authorization: Token <your_token>
```

```http
# Поиск с сортировкой
GET /s-api/signals-raw/?search=sequoia&ordering=-created_at
Authorization: Token <your_token>
```

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "http://localhost:8000/s-api/signals-raw/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "is_processed": false,
      "source_id": 5,
      "signal_type_id": 1,
      "data": {},
      "label": "project",
      "category": "ai",
      "stage": "seed",
      "round": "seed",
      "website": "https://example.com",
      "description": "Project description",
      "signal_card_id": null,
      "signal_id": null,
      "error_message": null,
      "created_at": "2025-12-30T10:00:00Z",
      "processed_at": null,
      "updated_at": "2025-12-30T10:00:00Z"
    }
  ]
}
```

#### `POST /s-api/signals-raw/`

Создать новый сырой сигнал (используется микросервисом сбора данных).

**Request:**
```http
POST /s-api/signals-raw/
Authorization: Token <your_token>
Content-Type: application/json

{
  "source_id": 5,
  "signal_type_id": 1,
  "data": {},
  "label": "project",
  "category": "ai",
  "stage": "seed",
  "round": "seed",
  "website": "https://example.com",
  "description": "Project description"
}
```

**Обязательные поля:**
- `data` - JSON объект с сырыми данными

**Опциональные поля:**
- `source_id` - ID источника
- `signal_type_id` - ID типа сигнала
- `label` - Базовая метка классификации (project/noise/uncertain)
- `category` - Категория (ai, fintech, etc.)
- `stage` - Стадия (seed, ideation, etc.)
- `round` - Раунд (seed, series-a, etc.)
- `website` - URL веб-сайта проекта
- `description` - Описание проекта

**Response (201 Created):**
```json
{
  "id": 1,
  "is_processed": false,
  "source_id": 5,
  "signal_type_id": 1,
  "data": {},
  "label": "project",
  "category": "ai",
  "stage": "seed",
  "round": "seed",
  "website": "https://example.com",
  "description": "Project description",
  "signal_card_id": null,
  "signal_id": null,
  "error_message": null,
  "created_at": "2025-12-30T10:00:00Z",
  "processed_at": null,
  "updated_at": "2025-12-30T10:00:00Z"
}
```

#### `GET /s-api/signals-raw/{id}/`

Получить конкретный сырой сигнал.

#### `PATCH /s-api/signals-raw/{id}/`

Обновить сырой сигнал.

**Request:**
```http
PATCH /s-api/signals-raw/1/
Authorization: Token <your_token>
Content-Type: application/json

{
  "is_processed": true,
  "signal_card_id": 10,
  "signal_id": 25
}
```

#### `DELETE /s-api/signals-raw/{id}/`

Удалить сырой сигнал.

---

#### Workflow использования SignalRaw:

**Шаг 1: Микросервис собирает данные и отправляет**
```http
POST /s-api/signals-raw/
Authorization: Token <service_token>
Content-Type: application/json

{
  "source_id": 5,
  "signal_type_id": 1,
  "data": {},
  "label": "project",
  "stage": "seed",
  "description": "Investment signal description"
}
```

**Шаг 2: Backend/обработчик читает необработанные сигналы**
```http
GET /s-api/signals-raw/?is_processed=false&ordering=created_at
Authorization: Token <your_token>
```

**Шаг 3: Обработчик создаёт SignalCard и Signal**
```python
# Ваша логика обработки
# 1. Парсинг данных из raw_signal.data
# 2. Создание или поиск SignalCard
# 3. Создание Signal
# 4. Обновление связей в SignalRaw
```

**Шаг 4: Обновление связей и отметка как обработанный**
```http
PATCH /s-api/signals-raw/1/
Authorization: Token <your_token>
Content-Type: application/json

{
  "is_processed": true,
  "signal_card_id": 15,
  "signal_id": 30
}
```

**Response:**
```json
{
  "id": 1,
  "is_processed": true,
  "signal_card_id": 15,
  "signal_id": 30,
  "processed_at": "2025-12-30T10:05:00Z",
  ...
}
```

#### Обработка ошибок:

Если обработка не удалась, сохраните сообщение об ошибке:

```http
PATCH /s-api/signals-raw/1/
Authorization: Token <your_token>
Content-Type: application/json

{
  "error_message": "Не удалось идентифицировать проект: недостаточно данных в поле description"
}
```

---

## Фильтрация и поиск

### Общие параметры фильтрации

Большинство endpoints поддерживают следующие параметры:

#### Search (Поиск)
```http
GET /s-api/participants/?search=sequoia
```
Ищет по названию, slug и другим текстовым полям.

#### Ordering (Сортировка)
```http
GET /s-api/signal-cards/?ordering=-created_at
```
- `ordering=name` - по возрастанию
- `ordering=-name` - по убыванию
- Доступные поля: `id`, `name`, `created_at`, `updated_at` и др.

#### Фильтры по полям
```http
GET /s-api/sources/?source_type=1&network=twitter&status=active
```

#### Комбинирование фильтров
```http
GET /s-api/signal-cards/?stage=seed&is_open=true&category=1&ordering=-created_at
```

---

## Пагинация

Все list endpoints возвращают пагинированные результаты.

### Параметры пагинации:
- `page` - номер страницы (по умолчанию 1)
- `page_size` - количество записей на странице (по умолчанию 20, максимум 100)

### Пример:
```http
GET /s-api/participants/?page=2&page_size=50
Authorization: Token <your_token>
```

### Формат ответа:
```json
{
  "count": 150,
  "next": "http://localhost:8000/s-api/participants/?page=3&page_size=50",
  "previous": "http://localhost:8000/s-api/participants/?page=1&page_size=50",
  "results": [...]
}
```

**Поля:**
- `count` - общее количество записей
- `next` - URL следующей страницы (null если это последняя)
- `previous` - URL предыдущей страницы (null если это первая)
- `results` - массив результатов

---

## Коды ответов

### Успешные ответы

- **200 OK** - Успешный GET/PATCH/PUT запрос
- **201 Created** - Успешное создание объекта (POST)
- **204 No Content** - Успешное удаление (DELETE)

### Ошибки клиента (4xx)

- **400 Bad Request** - Неверные данные запроса
  ```json
  {
    "field_name": ["Error message"]
  }
  ```

- **401 Unauthorized** - Отсутствует или неверный токен
  ```json
  {
    "detail": "Authentication credentials were not provided."
  }
  ```

- **403 Forbidden** - Нет прав доступа
  ```json
  {
    "detail": "You do not have permission to perform this action."
  }
  ```

- **404 Not Found** - Объект не найден
  ```json
  {
    "detail": "Not found."
  }
  ```

### Ошибки сервера (5xx)

- **500 Internal Server Error** - Внутренняя ошибка сервера
  ```json
  {
    "error": "internal_server_error",
    "message": "Internal server error"
  }
  ```

---

## Примеры использования

### Пример 1: Создание полного проекта с командой

**Шаг 1: Создать проект**
```http
POST /s-api/signal-cards/
Authorization: Token <your_token>
Content-Type: application/json

{
  "slug": "my-startup",
  "name": "My Startup",
  "description": "AI-powered platform for...",
  "stage": "seed",
  "round": "seed",
  "website": "https://mystartup.com",
  "is_open": true,
  "category": 1
}
```

Получаем ID проекта: `100`

**Шаг 2: Добавить членов команды**
```http
POST /s-api/team-members/
Authorization: Token <your_token>
Content-Type: application/json

{
  "name": "John Smith",
  "role": "CEO & Founder",
  "signal_card": 100
}
```

```http
POST /s-api/team-members/
Authorization: Token <your_token>
Content-Type: application/json

{
  "name": "Jane Doe",
  "role": "CTO & Co-Founder",
  "signal_card": 100
}
```

### Пример 2: Создание сигнала об инвестиции

**Шаг 1: Найти проект**
```http
GET /s-api/signal-cards/?search=my-startup
Authorization: Token <your_token>
```

**Шаг 2: Найти фонд (участника)**
```http
GET /s-api/participants/?participant_type=fund&search=sequoia
Authorization: Token <your_token>
```

**Шаг 3: Создать сигнал**
```http
POST /s-api/signals/
Authorization: Token <your_token>
Content-Type: application/json

{
  "signal_type": 1,
  "signal_card": 100,
  "participant": 5,
  "date": "2025-12-30",
  "amount": "2000000.00",
  "privacy": "public"
}
```

### Пример 3: Получение всех инвестиций в проект

```http
GET /s-api/signals/?signal_card=100&ordering=-date
Authorization: Token <your_token>
```

### Пример 4: Поиск всех проектов на стадии seed с фильтрами

```http
GET /s-api/signal-cards/?stage=seed&is_open=true&category=1&ordering=-created_at&page_size=20
Authorization: Token <your_token>
```

### Пример 5: Обновление статуса проекта

```http
PATCH /s-api/signal-cards/100/
Authorization: Token <your_token>
Content-Type: application/json

{
  "stage": "series-a",
  "round": "series-a",
  "is_open": false
}
```

---

## 🔧 Техническая информация

### Используемые технологии:
- Django 4.x
- Django REST Framework 3.x
- Token Authentication
- PostgreSQL

### Разрешения:
Все endpoints требуют `IsAdminUserWithToken` permission - пользователь должен быть администратором и иметь валидный токен.

### Лимиты:
- Максимальный `page_size`: 100
- По умолчанию `page_size`: 20

---

## 📞 Поддержка

Если у вас есть вопросы или проблемы с API, обратитесь к:
- Технической документации в папке `signals/`
- `.http` файлам с примерами запросов
- Администратору системы

---

**Версия документации:** 1.0  
**Дата обновления:** 30 декабря 2025
