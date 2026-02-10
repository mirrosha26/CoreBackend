# Документация GraphQL приложения

## Обзор

Это GraphQL приложение предоставляет комплексный API для платформы мониторинга венчурного капитала, построенный на базе **Strawberry GraphQL** и **Django**. Оно предлагает расширенные возможности запросов для карточек сигналов, участников, категорий и управления пользователями с обширными оптимизациями производительности и стратегиями кэширования.

## Архитектура

### Основные компоненты

```
graphql_app/
├── schema.py              # Основная GraphQL схема с DjangoOptimizerExtension
├── queries.py             # Все резолверы запросов (2,746 строк)
├── mutations.py           # Все резолверы мутаций (1,412 строк)
├── types.py               # Определения GraphQL типов (1,427 строк)
├── performance.py         # Мониторинг производительности и метрики
├── query_complexity.py    # Анализ сложности запросов и ограничения
├── dataloaders.py         # Реализации DataLoader для предотвращения N+1 проблем
├── query_caching.py       # Стратегии кэширования на уровне запросов
├── comprehensive_query_caching.py  # Расширенное кэширование для сложных запросов
├── enhanced_prefetching.py         # Интеллектуальная предзагрузка из БД
├── enhanced_bulk_loading.py        # Оптимизации массовой загрузки
├── optimized_signal_resolver.py    # Оптимизированный резолвер полей сигналов
├── optimized_user_context.py       # Оптимизация пользовательского контекста
└── urls.py                # Маршрутизация URL
```

### Ключевые возможности

- **Мониторинг производительности** - Отслеживание производительности запросов в реальном времени
- **Анализ сложности запросов** - Предотвращение дорогостоящих операций
- **Многоуровневое кэширование** - Кэширование запросов, полей и комплексное кэширование
- **DataLoaders** - Эффективная пакетная загрузка для предотвращения N+1 запросов
- **Умная предзагрузка** - Динамическая загрузка связей на основе GraphQL запроса
- **Контроль приватности** - Детальный контроль доступа для приватных участников
- **Региональная фильтрация** - Группировка и фильтрация по географическому местоположению
- **Пользовательские предпочтения** - Фильтрация по предпочтениям отображения WEB2/WEB3/ALL
- **Расширенный поиск** - Полнотекстовый поиск с оценкой релевантности
- **Гибкая пагинация** - Традиционная и Relay-стиль курсорная пагинация

## Main Query Types

### 1. Карточки сигналов (`signalCards`)

**Назначение**: Получение пагинированных карточек сигналов с расширенной фильтрацией и оптимизацией

**Ключевые возможности**:

- Расширенная фильтрация (категории, участники, стадии, местоположения и т.д.)
- Поиск с оценкой релевантности
- Поддержка папок (параметр `folder_key`)
- Фильтрация приватности для приватных участников
- Пользовательские предпочтения отображения (WEB2/WEB3/ALL)
- Интеллектуальное кэширование на основе сложности запроса

**Пример использования**:

```graphql
query GetSignalCards {
  signalCards(
    filters: {
      search: "AI стартап"
      categories: ["1", "2"]
      stages: ["seed", "series_a"]
      featured: true
    }
    pagination: { page: 1, page_size: 20 }
    sort_by: LATEST_SIGNAL_DATE
    include_signals: true
  ) {
    nodes {
      id
      name
      slug
      description
      stage
      signals {
        id
        description
        participant {
          name
          type
        }
      }
    }
    total_count
    has_next_page
    current_page
  }
}
```

### 2. Лента пользователя (`userFeed`)

**Назначение**: Персонализированная лента, показывающая все доступные карточки сигналов с пользовательской фильтрацией

**Ключевые возможности**:

- Показывает ВСЕ доступное содержимое (не только отслеживаемых участников)
- Фильтрация приватности учитывает доступ пользователя к участникам
- Персональные предпочтения ленты (категории, стадии, местоположения)
- Опция обхода персональных фильтров (`bypass_personal_filters`)
- Оптимизировано для массовой загрузки с комплексным кэшированием

**Пример использования**:

```graphql
query GetUserFeed {
  userFeed(
    pagination: { page: 1, page_size: 20 }
    include_signals: true
    bypass_personal_filters: false
  ) {
    nodes {
      id
      name
      latest_signal_date
      signals {
        participant {
          name
          is_private
        }
      }
    }
    total_count
  }
}
```

### 3. Участники (`participants`)

**Назначение**: Пагинированные участники с умным поиском и обработкой приватности

**Ключевые возможности**:

- Relay-стиль курсорная пагинация
- Умный поиск с логикой включения фондов
- Фильтрация приватности (публичные + приватные участники пользователя)
- Фильтрация по типу (фонды, ангелы, инвесторы и т.д.)
- Расширенная логика поиска, включающая связанные фонды

**Пример использования**:

```graphql
query GetParticipants {
  participants(
    first: 20
    search: "andreessen"
    funds_only: false
    types: ["investor", "fund"]
  ) {
    edges {
      node {
        id
        name
        type
        is_private
        associated_with {
          id
          name
        }
      }
      cursor
    }
    page_info {
      has_next_page
      end_cursor
    }
    total_count
  }
}
```

### 4. Умный поиск участников (`smartParticipantSearch`)

**Назначение**: Расширенный поиск участников, который интеллектуально включает фонды

**Ключевые возможности**:

- Ищет физических лиц и автоматически включает их связанные фонды
- Дедупликация для избежания показа одного и того же фонда несколько раз
- Опция включения/исключения индивидуальных участников
- Поиск с учетом приватности результатов

**Пример использования**:

```graphql
query SmartSearch {
  smartParticipantSearch(
    search: "a16z"
    include_individuals: true
  ) {
    id
    name
    type
    is_private
  }
}
```

### 5. Региональные местоположения (`regionalLocations`)

**Назначение**: Географическая фильтрация с региональной группировкой

**Ключевые возможности**:

- Группирует местоположения по регионам (Северная Америка, Европа, Азия и т.д.)
- Показывает только регионы, существующие в базе данных
- Отслеживание активного состояния для UI компонентов
- Поддержка частичного выбора регионов

**Пример использования**:

```graphql
query GetRegionalLocations {
  regionalLocations(active_locations: ["North America", "Europe"]) {
    regional_mappings {
      name
      slug
    }
    filter_options {
      name
      slug
      active
      is_region
      partially_active
    }
  }
}
```

### 6. Сохраненные фильтры (`savedFilters`)

**Назначение**: Сохраненные конфигурации фильтров пользователя

**Ключевые возможности**:

- Фильтрация по текущему предпочтению отображения сигналов пользователя
- Поддержка пагинации
- Опциональный подсчет количества недавних проектов
- Идентификация фильтра по умолчанию

**Пример использования**:

```graphql
query GetSavedFilters {
  savedFilters(
    pagination: { page: 1, page_size: 10 }
    include_recent_counts: true
  ) {
    nodes {
      id
      name
      is_default
      categories {
        name
      }
      participants {
        name
      }
      recent_projects_count
    }
  }
}
```

### 7. Категории (`categories`)

**Назначение**: Получение списка всех категорий с поддержкой фильтрации

**Ключевые возможности**:

- Получение всех категорий или фильтрация по типу
- Поддержка вложенных категорий (родительские и дочерние)
- Фильтрация по предпочтениям отображения пользователя

**Пример использования**:

```graphql
query GetCategories {
  categories {
    id
    name
    slug
    parent {
      id
      name
    }
    children {
      id
      name
    }
  }
}
```

### 8. Текущий пользователь (`me`)

**Назначение**: Получение информации о текущем аутентифицированном пользователе

**Ключевые возможности**:

- Информация о профиле пользователя
- Предпочтения отображения сигналов
- Статистика и настройки

**Пример использования**:

```graphql
query GetCurrentUser {
  me {
    id
    username
    email
    signal_display_preference
    date_joined
  }
}
```

## Расширенные возможности

### Оптимизация производительности

#### Анализ сложности запросов

- Автоматическая оценка сложности на основе весов полей
- Предотвращение перегрузки системы дорогостоящими запросами
- Настраиваемые ограничения сложности и ограничения глубины

#### Многоуровневая стратегия кэширования

1. **Кэширование на уровне запросов** - Кэширует полные результаты запросов для дорогостоящих операций
2. **Кэширование на уровне полей** - Кэширует вычисления отдельных полей
3. **Комплексное кэширование** - Расширенное кэширование для сложных запросов ленты

#### DataLoaders

- Пакетная загрузка для участников, категорий и сигналов
- Предотвращение проблем N+1 запросов
- Автоматическая пакетизация и дедупликация

#### Расширенная предзагрузка

- Динамически определяет связи для предзагрузки на основе GraphQL запроса
- Уменьшает количество обращений к базе данных
- Оптимизирует использование select_related и prefetch_related

#### Массовая загрузка

- Эффективная загрузка больших наборов данных
- Минимизация количества запросов к БД
- Оптимизация для работы с большими объемами данных

### Приватность и безопасность

#### Фильтрация приватности

- **Публичные участники**: Видны всем пользователям
- **Приватные участники**: Видны только пользователям, которые их создали/запросили
- Единая логика приватности во всех запросах

#### Пользовательские предпочтения отображения

- **ALL**: Показывает все карточки сигналов
- **WEB2**: Исключает web3 категории и подкатегории
- **WEB3**: Показывает только web3 категории и подкатегории

### Система фильтрации

#### Расширенная фильтрация участников

```graphql
input ParticipantFilter {
  mode: ParticipantFilterMode # INCLUDE_ONLY, EXCLUDE_FROM_TYPE
  participantIds: [ID!]
  participantTypes: [String!]
}
```

**Режимы фильтрации**:
- `INCLUDE_ONLY` - Включить только указанных участников
- `EXCLUDE_FROM_TYPE` - Исключить участников определенных типов

#### Фильтрация по датам

- Гибкий ввод дат с поддержкой множества форматов (DD.MM.YYYY, YYYY-MM-DD и т.д.)
- Пользовательский скаляр FlexibleDate для единообразной обработки дат
- Поддержка диапазонов дат для фильтрации сигналов

#### Возможности поиска

- Полнотекстовый поиск по множеству полей
- Оценка релевантности для результатов поиска
- Упорядочивание результатов поиска по релевантности + вторичным критериям

#### Фильтрация по стадиям

- Фильтрация по стадиям финансирования (seed, series_a, series_b и т.д.)
- Поддержка множественного выбора стадий
- Комбинирование с другими фильтрами

#### Фильтрация по местоположению

- Фильтрация по регионам
- Поддержка множественного выбора местоположений
- Региональная группировка для удобства

## Операции мутаций

### Управление карточками

#### `saveCardToFolder`

Сохраняет карточки в папки пользователя.

**Параметры**:
- `card_id` (ID!) - ID карточки для сохранения
- `folder_key` (String) - Ключ папки (опционально)

**Пример**:

```graphql
mutation SaveCard {
  saveCardToFolder(card_id: "123", folder_key: "favorites") {
    success
    message
  }
}
```

#### `removeCardFromFolder`

Удаляет карточки из папок.

**Параметры**:
- `card_id` (ID!) - ID карточки для удаления
- `folder_key` (String) - Ключ папки (опционально)

#### `deleteCard`

Мягкое удаление карточек (добавляет в список удаленных).

**Параметры**:
- `card_id` (ID!) - ID карточки для удаления

#### `restoreCard`

Восстанавливает удаленные карточки.

**Параметры**:
- `card_id` (ID!) - ID карточки для восстановления

### Управление заметками

#### `addNoteToCard`

Добавляет заметки к карточкам сигналов.

**Параметры**:
- `card_id` (ID!) - ID карточки
- `note_text` (String!) - Текст заметки

**Пример**:

```graphql
mutation AddNote {
  addNoteToCard(card_id: "123", note_text: "Интересный проект") {
    success
    message
    note {
      id
      text
      created_at
    }
  }
}
```

#### `updateCardNote`

Обновляет существующие заметки.

**Параметры**:
- `note_id` (ID!) - ID заметки
- `note_text` (String!) - Новый текст заметки

#### `removeNoteFromCard`

Удаляет заметки.

**Параметры**:
- `note_id` (ID!) - ID заметки для удаления

### Управление фильтрами

#### `saveCurrentFilters`

Сохраняет текущее состояние фильтров.

**Параметры**:
- `name` (String!) - Имя сохраненного фильтра
- `is_default` (Boolean) - Установить как фильтр по умолчанию
- `filters` (FilterInput!) - Объект с параметрами фильтров

#### `clearFilters`

Очищает все активные фильтры.

#### `updateFilter`

Обновляет конкретные значения фильтров.

#### `createSavedFilter`

Создает новый сохраненный фильтр.

**Параметры**:
- `name` (String!) - Имя фильтра
- `filters` (FilterInput!) - Параметры фильтров
- `is_default` (Boolean) - Установить как фильтр по умолчанию

#### `updateSavedFilter`

Обновляет существующий сохраненный фильтр.

**Параметры**:
- `filter_id` (ID!) - ID фильтра
- `name` (String) - Новое имя (опционально)
- `filters` (FilterInput) - Новые параметры (опционально)
- `is_default` (Boolean) - Установить как фильтр по умолчанию (опционально)

#### `deleteSavedFilter`

Удаляет сохраненный фильтр.

**Параметры**:
- `filter_id` (ID!) - ID фильтра для удаления

### Управление папками

#### `createUserFolder`

Создает новые папки пользователя.

**Параметры**:
- `name` (String!) - Имя папки
- `key` (String!) - Уникальный ключ папки
- `description` (String) - Описание папки (опционально)

**Пример**:

```graphql
mutation CreateFolder {
  createUserFolder(
    name: "Избранное"
    key: "favorites"
    description: "Мои любимые проекты"
  ) {
    success
    message
    folder {
      id
      name
      key
    }
  }
}
```

#### `updateUserFolder`

Обновляет свойства папки.

**Параметры**:
- `folder_id` (ID!) - ID папки
- `name` (String) - Новое имя (опционально)
- `description` (String) - Новое описание (опционально)

#### `deleteUserFolder`

Удаляет папки.

**Параметры**:
- `folder_id` (ID!) - ID папки для удаления

#### `setDefaultFolder`

Устанавливает папку по умолчанию для пользователя.

**Параметры**:
- `folder_key` (String!) - Ключ папки

## Примеры использования

### Сложный запрос с множеством возможностей

```graphql
query ComplexSignalCardsQuery {
  signalCards(
    filters: {
      search: "AI fintech стартап"
      categories: ["1", "5", "8"]
      participant_filter: {
        mode: EXCLUDE_FROM_TYPE
        participantTypes: ["angel", "investor"]
        participantIds: ["123", "456"]
      }
      stages: ["seed", "series_a"]
      locations: ["United States", "United Kingdom"]
      featured: true
      start_date: "01.01.2024"
      end_date: "31.12.2024"
      min_signals: 3
    }
    pagination: { page: 1, page_size: 20 }
    sort_by: LATEST_SIGNAL_DATE
    sort_order: DESC
    include_signals: true
  ) {
    nodes {
      id
      name
      slug
      description
      stage
      round_status
      location
      featured
      latest_signal_date
      signals(limit: 5) {
        id
        description
        created_at
        participant {
          id
          name
          type
          is_private
        }
        associated_participant {
          id
          name
          type
        }
      }
      categories {
        id
        name
        slug
      }
      is_saved
      is_noted
      note_text
    }
    total_count
    has_next_page
    has_previous_page
    current_page
    total_pages
  }
}
```

### Комплексный запрос пользовательского контекста

```graphql
query UserDashboard {
  me {
    id
    username
    email
    signal_display_preference
  }

  userFeed(pagination: { page: 1, page_size: 10 }, include_signals: true) {
    nodes {
      id
      name
      stage
      signals(limit: 3) {
        participant {
          name
          type
        }
      }
    }
    total_count
  }

  savedFilters {
    nodes {
      id
      name
      is_default
      categories {
        name
      }
    }
  }

  categories {
    id
    name
    slug
  }
}
```

### Пример работы с мутациями

```graphql
mutation ManageCard {
  # Сохранение карточки в папку
  saveCard: saveCardToFolder(
    card_id: "123"
    folder_key: "favorites"
  ) {
    success
    message
  }

  # Добавление заметки
  addNote: addNoteToCard(
    card_id: "123"
    note_text: "Очень интересный проект в области AI"
  ) {
    success
    note {
      id
      text
    }
  }

  # Создание сохраненного фильтра
  createFilter: createSavedFilter(
    name: "AI проекты"
    is_default: false
    filters: {
      categories: ["1", "5"]
      stages: ["seed", "series_a"]
    }
  ) {
    success
    filter {
      id
      name
    }
  }
}
```

## Соображения по производительности

### Ограничения сложности запросов

- Максимальная сложность по умолчанию: 1000
- Максимальная глубина по умолчанию: 15
- Сложность интроспекции: 100

### Значения TTL кэширования

- Легкие запросы: Без кэширования (вычисляются напрямую)
- Умеренные запросы: 5 минут
- Тяжелые запросы: 15 минут
- Комплексные запросы: 30 минут

### Рекомендации по использованию

1. **Используйте include_signals экономно** - Только когда вам нужны данные сигналов
2. **Ограничивайте размер пагинации** - Максимум 100 элементов на страницу
3. **Предпочитайте конкретные фильтры** - Более конкретные фильтры обеспечивают лучшее кэширование
4. **Используйте курсорную пагинацию** - Для больших наборов результатов
5. **Мониторьте сложность запросов** - Проверяйте предупреждения о сложности в ответах
6. **Используйте DataLoaders** - Автоматически предотвращают N+1 проблемы
7. **Оптимизируйте поля запросов** - Запрашивайте только необходимые поля

### Метрики производительности

Система отслеживает следующие метрики:

- Время выполнения запросов
- Количество запросов к базе данных
- Коэффициент попаданий в кэш
- Использование памяти
- Сложность запросов

## Обработка ошибок

### Типы ошибок

#### `QueryComplexityError`

Запрос превышает ограничения сложности.

```json
{
  "errors": [{
    "message": "Сложность запроса (1200) превышает максимально допустимую (1000)",
    "extensions": {
      "code": "QUERY_COMPLEXITY_ERROR",
      "complexity": 1200,
      "max_allowed": 1000
    }
  }]
}
```

#### `AuthenticationError`

Пользователь не аутентифицирован для защищенных операций.

```json
{
  "errors": [{
    "message": "Требуется аутентификация",
    "extensions": {
      "code": "AUTHENTICATION_ERROR"
    }
  }]
}
```

#### `ValidationError`

Недопустимые входные параметры.

```json
{
  "errors": [{
    "message": "Недопустимое значение для поля 'page_size'",
    "extensions": {
      "code": "VALIDATION_ERROR",
      "field": "page_size"
    }
  }]
}
```

#### `PrivacyError`

Попытка доступа к приватным ресурсам.

```json
{
  "errors": [{
    "message": "Доступ к приватному участнику запрещен",
    "extensions": {
      "code": "PRIVACY_ERROR"
    }
  }]
}
```

#### `NotFoundError`

Запрашиваемый ресурс не найден.

```json
{
  "errors": [{
    "message": "Карточка с ID '123' не найдена",
    "extensions": {
      "code": "NOT_FOUND_ERROR"
    }
  }]
}
```

### Формат ответа с ошибками

Все ошибки возвращаются в стандартном формате GraphQL:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Описание ошибки",
      "extensions": {
        "code": "ERROR_CODE",
        "additional_info": "Дополнительная информация"
      },
      "path": ["fieldName", 0, "nestedField"]
    }
  ]
}
```

## Конфигурация

### Переменные окружения

```python
# GraphQL Конфигурация
GRAPHQL_MAX_COMPLEXITY = 1000          # Максимальная сложность запроса
GRAPHQL_MAX_DEPTH = 15                 # Максимальная глубина вложенности
GRAPHQL_INTROSPECTION_COMPLEXITY = 100  # Сложность для интроспекции

# Конфигурация кэширования
GRAPHQL_CACHE_TTL_MODERATE = 300       # 5 минут для умеренных запросов
GRAPHQL_CACHE_TTL_HEAVY = 900          # 15 минут для тяжелых запросов
GRAPHQL_CACHE_TTL_COMPREHENSIVE = 1800 # 30 минут для комплексных запросов

# Мониторинг производительности
GRAPHQL_ENABLE_PERFORMANCE_MONITORING = True  # Включить мониторинг
GRAPHQL_LOG_SLOW_QUERIES = True               # Логировать медленные запросы
GRAPHQL_SLOW_QUERY_THRESHOLD = 1000           # Порог медленного запроса (мс)
```

### Настройка кэширования

Кэширование можно настроить через Django settings:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### Настройка DataLoaders

DataLoaders автоматически используются для:
- Загрузки участников
- Загрузки категорий
- Загрузки сигналов
- Загрузки связей между сущностями

## Тестирование

### GraphQL Playground

Доступ к GraphQL playground находится по адресу `/graphql/` для интерактивного тестирования запросов и исследования схемы.

**Возможности Playground**:
- Интерактивное выполнение запросов
- Автодополнение полей и типов
- Просмотр документации схемы
- История запросов
- Переменные запросов

### Тестирование производительности

Используйте декоратор `@monitor_query_performance` на резолверах для отслеживания:

- Время выполнения
- Количество запросов к БД
- Коэффициент попаданий/промахов кэша
- Использование памяти

**Пример использования**:

```python
from graphql_app.performance import monitor_query_performance

@monitor_query_performance
def resolve_signal_cards(self, info, ...):
    # Ваш код резолвера
    pass
```

### Тестирование сложности

Проверьте сложность запроса с помощью интроспекции:

```graphql
query IntrospectComplexity {
  __schema {
    queryType {
      fields {
        name
        type {
          name
        }
      }
    }
  }
}
```

### Интеграционное тестирование

Пример теста для проверки запроса:

```python
from django.test import TestCase
from graphql_app.schema import schema

class SignalCardsTestCase(TestCase):
    def test_signal_cards_query(self):
        query = """
        query {
          signalCards(pagination: { page: 1, page_size: 10 }) {
            nodes {
              id
              name
            }
            total_count
          }
        }
        """
        result = schema.execute_sync(query)
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
```

## Структура данных

### Основные типы

#### SignalCard

```graphql
type SignalCard {
  id: ID!
  name: String!
  slug: String!
  description: String
  stage: String
  round_status: String
  location: String
  featured: Boolean!
  latest_signal_date: DateTime
  signals: [Signal!]!
  categories: [Category!]!
  is_saved: Boolean!
  is_noted: Boolean!
  note_text: String
}
```

#### Participant

```graphql
type Participant {
  id: ID!
  name: String!
  type: String!
  is_private: Boolean!
  associated_with: [Participant!]!
}
```

#### Signal

```graphql
type Signal {
  id: ID!
  description: String!
  created_at: DateTime!
  participant: Participant!
  associated_participant: Participant
}
```

#### Category

```graphql
type Category {
  id: ID!
  name: String!
  slug: String!
  parent: Category
  children: [Category!]!
}
```

## Миграция и обновления

### Обновление схемы

При изменении схемы GraphQL:

1. Обновите типы в `types.py`
2. Обновите резолверы в `queries.py` или `mutations.py`
3. Обновите документацию
4. Протестируйте изменения
5. Очистите кэш при необходимости

### Обратная совместимость

- Новые поля добавляются как опциональные
- Устаревшие поля помечаются как `@deprecated`
- Изменения в типах ввода требуют версионирования

## Поддержка и контакты

Для вопросов и поддержки обращайтесь к команде разработки или создайте issue в репозитории проекта.

---

Эта документация охватывает комплексный GraphQL API, построенный для платформы мониторинга венчурного капитала, демонстрируя расширенные возможности для оптимизации производительности, безопасности и пользовательского опыта.
