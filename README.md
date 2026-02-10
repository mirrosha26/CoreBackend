# CoreBackend - Платформа мониторинга венчурного капитала

## Описание проекта

CoreBackend представляет собой комплексную Django-платформу для мониторинга и анализа венчурного капитала. Система предоставляет инструменты для отслеживания сигналов инвесторов, управления проектами, участниками (фондами, инвесторами) и реализует несколько API интерфейсов для различных типов клиентов.

### Основные возможности

- Отслеживание сигналов — автоматический сбор и анализ сигналов интереса инвесторов к проектам
- Управление проектами — карточки сигналов с детальной информацией о стартапах
- Управление участниками — фонды, инвесторы, ангелы и другие участники экосистемы
- Персонализация — папки, фильтры, заметки для организации работы пользователей
- Многоуровневая аутентификация — различные типы токенов для разных клиентов
- Аналитика — статистика и метрики по проектам и участникам
- Множественные API — REST и GraphQL интерфейсы для различных сценариев использования

---

## Архитектура проекта

Проект построен на базе Django 5.0 и состоит из нескольких модулей, каждый из которых предоставляет специализированный API:

```
CoreBackend/
├── client_api/          # REST API для внешних интеграций
├── frontend_api/        # REST API для веб-приложения
├── graphql_app/         # GraphQL API с оптимизациями
├── signals/            # Внутреннее сервисное API
├── profile/            # Модели пользователей и групп
├── notifications/      # Система уведомлений
└── config/             # Конфигурация Django
```

---

## Документация модулей

Проект включает подробную документацию для каждого API модуля:

### 1. Client API

**RESTful интерфейс для внешних интеграций**

- Базовый URL: `http://localhost:8000/client_api/`
- Аутентификация: Token-based (`Authorization: Token <your_token>`)
- Назначение: Интеграция в системы мониторинга венчурного капитала
- Основные возможности:
  - Получение карточек проектов с фильтрацией и сортировкой
  - Управление участниками (фонды, инвесторы)
  - Справочные данные (категории, стадии, раунды)
  - Пагинация и расширенная фильтрация
  - Rate limiting (100-500 запросов в зависимости от типа доступа)

[Полная документация Client API](./client_api/README.md)

---

### 2. Frontend API

**RESTful интерфейс для веб-приложения**

- Базовый URL: `http://localhost:8000/frontend_api/`
- Аутентификация: JWT токены (`Authorization: Bearer <access_token>`)
- Назначение: Полнофункциональный API для веб-приложения
- Основные возможности:
  - Аутентификация и управление пользователями
  - Управление карточками (избранное, заметки, папки)
  - Сохраненные фильтры и настройки дайджеста
  - Управление папками и экспорт данных
  - Групповые назначения и тикеты
  - Публичные карточки

[Полная документация Frontend API](./frontend_api/README.md)

---

### 3. GraphQL API

**GraphQL интерфейс с оптимизациями производительности**

- Базовый URL: `http://localhost:8000/graphql/`
- Аутентификация: JWT токены
- Назначение: Гибкий GraphQL API с расширенными возможностями
- Основные возможности:
  - Запросы карточек сигналов с расширенной фильтрацией
  - Персонализированная лента пользователя
  - Умный поиск участников
  - Региональная фильтрация
  - Многоуровневое кэширование
  - DataLoaders для предотвращения N+1 проблем
  - Мониторинг производительности и анализ сложности запросов

[Полная документация GraphQL API](./graphql_app/README.md)

---

### 4. Signals API

**Внутреннее сервисное API для администраторов и микросервисов**

- Базовый URL: `http://localhost:8000/s-api/`
- Аутентификация: Token-based
- Назначение: Управление данными и интеграция с микросервисами
- Основные возможности:
  - CRUD операции для всех моделей
  - Управление источниками данных
  - Приём сырых данных от микросервисов (SignalRaw)
  - Управление участниками, проектами, категориями
  - Управление сигналами и членами команд
  - Расширенная фильтрация и поиск

[Полная документация Signals API](./signals/README.md)

---

## Быстрый старт

### Требования

- Python 3.8+
- PostgreSQL — основная база данных (обязательно)
- Redis (для кэширования, опционально)

### Установка

1. Клонирование репозитория

```bash
git clone <repository-url>
cd CoreBackend
```

2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

3. Установка зависимостей

```bash
pip install -r requirements.txt
```

4. Настройка базы данных

Проект использует PostgreSQL в качестве основной базы данных. Убедитесь, что PostgreSQL установлен и запущен.

Создайте базу данных:

```sql
CREATE DATABASE corebackend_db;
```

Создайте файл `.env` в корне проекта:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/corebackend_db
SECRET_KEY=your-secret-key
DEBUG=True
```

5. Применение миграций

```bash
python manage.py migrate
```

6. Создание суперпользователя

```bash
python manage.py createsuperuser
```

7. Запуск сервера разработки

```bash
python manage.py runserver
```

Сервер будет доступен по адресу `http://localhost:8000/`

---

## Конфигурация

### Основные настройки

Проект использует `python-decouple` для управления переменными окружения. Основные настройки находятся в `config/settings.py`.

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# База данных (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/corebackend_db

# Безопасность
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis (опционально, для кэширования)
REDIS_URL=redis://localhost:6379/0

# GraphQL настройки
GRAPHQL_MAX_COMPLEXITY=1000
GRAPHQL_MAX_DEPTH=15

# Email (для уведомлений)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-password
```

---

## Основные зависимости

- Django 5.0 — веб-фреймворк
- Django REST Framework 3.14 — REST API
- Strawberry GraphQL — GraphQL API
- PostgreSQL — основная база данных (через psycopg2-binary)
- JWT — аутентификация (djangorestframework-simplejwt)
- Gunicorn — WSGI сервер для production

Полный список зависимостей см. в `requirements.txt`

---

## Структура проекта

```
CoreBackend/
├── client_api/              # Client API модуль
│   ├── README.md           # Документация Client API
│   ├── views.py            # Представления API
│   ├── serializers/        # Сериализаторы
│   └── authentication.py   # Аутентификация
│
├── frontend_api/           # Frontend API модуль
│   ├── README.md          # Документация Frontend API
│   ├── views/             # Представления
│   └── serializers/       # Сериализаторы
│
├── graphql_app/            # GraphQL модуль
│   ├── README.md          # Документация GraphQL API
│   ├── schema.py          # GraphQL схема
│   ├── queries.py         # Запросы
│   ├── mutations.py       # Мутации
│   └── types.py           # Типы
│
├── signals/               # Signals API модуль
│   ├── README.md         # Документация Signals API
│   ├── models.py         # Модели данных
│   ├── views.py          # Представления
│   └── filters.py        # Фильтры
│
├── profile/               # Модели пользователей
├── notifications/         # Система уведомлений
├── config/                # Конфигурация Django
│   ├── settings.py        # Настройки
│   ├── urls.py            # Главный URLconf
│   └── wsgi.py            # WSGI конфигурация
│
├── requirements.txt       # Зависимости Python
├── manage.py              # Django management script
└── README.md              # Этот файл
```

---

## Аутентификация

Проект поддерживает несколько типов аутентификации:

### 1. JWT токены (Frontend API, GraphQL)

Используется для веб-приложения. Access и Refresh токены. Эндпоинты: `/frontend_api/auth/login/`, `/frontend_api/auth/refresh/`

### 2. Token Authentication (Client API)

Используется для внешних интеграций. Токены выдаются администратором. Формат: `Authorization: Token <your_token>`

### 3. Token Authentication (Signals API)

Используется для внутренних сервисов. Токены для администраторов и микросервисов. Формат: `Authorization: Token <your_token>`

---

## Основные модели данных

### SignalCard (Карточка сигнала)

Проект/стартап, отслеживаемый в системе

### Participant (Участник)

Фонды, инвесторы, ангелы и другие участники экосистемы

### Signal (Сигнал)

Проявление интереса участника к проекту

### Category (Категория)

Категории проектов (иерархическая структура)

### Source (Источник)

Источники данных (социальные сети, профили)

---

## Тестирование

### Запуск тестов

```bash
python manage.py test
```

### Тестирование конкретного модуля

```bash
python manage.py test client_api
python manage.py test frontend_api
python manage.py test graphql_app
python manage.py test signals
```

---

## Развёртывание

### Production настройки

1. Настройте переменные окружения

```env
DEBUG=False
ALLOWED_HOSTS=your-domain.com
SECRET_KEY=production-secret-key
```

2. Соберите статические файлы

```bash
python manage.py collectstatic
```

3. Запуск с Gunicorn

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Или используйте конфигурацию из `gunicorn_config.py`:

```bash
gunicorn -c gunicorn_config.py config.wsgi:application
```

---

## Полезные ссылки

- [Документация Client API](./client_api/README.md)
- [Документация Frontend API](./frontend_api/README.md)
- [Документация GraphQL API](./graphql_app/README.md)
- [Документация Signals API](./signals/README.md)

---

Версия: 1.0.0  
Последнее обновление: 2024
