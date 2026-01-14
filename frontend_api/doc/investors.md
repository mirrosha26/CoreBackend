# Platform API

## Управление инвесторами

### Базовый URL
```
{{baseUrl}}/f-api/
```

### Эндпоинты управления инвесторами

#### 1. Получение списка инвесторов
```http
GET /investors/
Authorization: Bearer {{accessToken}}
```

**Параметры запроса:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `saved` | string | Фильтр по сохраненным инвесторам. Возможные значения: `true` (только сохраненные), `false` (несохраненные) |

**Описание:** Возвращает список инвесторов в соответствии с указанным фильтром.

**Ответ (успех):**
```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "name": "Имя инвестора",
      "additional_name": "Дополнительное имя",
      "type": "Тип инвестора",
      "about": "Описание инвестора",
      "slug": "investor-slug",
      "image": "http://example.com/media/investors/image.jpg",
      "num_cards": 5,
      "is_private": false
    },
    // Другие инвесторы...
  ]
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 2. Сохранение инвесторов в избранное
```http
POST /investors/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "participant_ids": [123, 456, 789]
}
```

**Описание:** Добавляет указанных инвесторов в список избранных пользователя.

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Saved 2 investors, 1 were already saved",
  "saved_count": 2,
  "already_saved_count": 1
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_PARAMETER` | Отсутствуют ID инвесторов |
| `INVALID_PARAMETER` | Некорректный формат параметра participant_ids |
| `INVESTOR_NOT_FOUND` | Один или несколько инвесторов не найдены |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 3. Удаление инвесторов из избранного
```http
DELETE /investors/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "participant_ids": [123, 456]
}
```

**Описание:** Удаляет указанных инвесторов из списка избранных пользователя.

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Removed 2 investors from saved",
  "deleted_count": 2
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_PARAMETER` | Отсутствуют ID инвесторов |
| `INVALID_PARAMETER` | Некорректный формат параметра participant_ids |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

### Эндпоинты управления приватными инвесторами

#### 1. Получение списка приватных инвесторов
```http
GET /investors/private/
Authorization: Bearer {{accessToken}}
```

**Описание:** Возвращает список приватных инвесторов пользователя и запросов на добавление, разделенных на три категории.

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "pending_requests": [
      {
        "id": 456,
        "name": "Имя запрашиваемого инвестора",
        "twitter_headline": "twitter_username",
        "product_hunt_headline": "producthunt_username",
        "linkedin_headline": "linkedin_username",
        "created_at": "2023-01-01T12:00:00Z"
      }
    ],
    "processing_requests": [
      {
        "id": 789,
        "name": "Имя инвестора в обработке",
        "twitter_headline": "twitter_username",
        "product_hunt_headline": "producthunt_username",
        "linkedin_headline": "linkedin_username",
        "participant_id": 321,
        "created_at": "2023-01-01T12:00:00Z"
      }
    ],
    "investors_with_signals": [
      {
        "id": 123,
        "name": "Имя приватного инвестора",
        "slug": "private-investor-slug",
        "type": "Тип инвестора",
        "is_private": true,
        "is_subscribed": true,
        "image": "http://example.com/media/investors/image.jpg",
        "num_cards": 7
      }
    ]
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 2. Создание запроса на добавление приватного инвестора
```http
POST /investors/private/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "name": "Имя инвестора",
  "additional_name": "Дополнительное имя",
  "twitter_headline": "twitter_username",
  "product_hunt_headline": "producthunt_username",
  "linkedin_headline": "linkedin_username"
}
```

**Описание:** Создает или обновляет запрос на добавление приватного инвестора.

**Ответ (успех при создании):**
```json
{
  "success": true,
  "message": "New request created successfully",
  "data": {
    "id": 123,
    "name": "Имя инвестора",
    "twitter_headline": "twitter_username"
  }
}
```

**Ответ (успех при обновлении):**
```json
{
  "success": true,
  "message": "Existing request updated successfully",
  "data": {
    "id": 123,
    "name": "Имя инвестора",
    "twitter_headline": "twitter_username"
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_PARAMETER` | Отсутствуют обязательные поля |
| `REQUEST_PROCESSED` | Запрос уже обработан |
| `SOURCE_EXISTS` | Источник уже существует |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 3. Удаление запроса на добавление приватного инвестора
```http
DELETE /investors/private/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "req_id": 123
}
```

**Описание:** Удаляет запрос на добавление приватного инвестора.

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Request deleted successfully"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_PARAMETER` | Отсутствует ID запроса |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 4. Загрузка CSV файла с приватными инвесторами
```http
POST /investors/private/csv-upload/
Authorization: Bearer {{accessToken}}
Content-Type: multipart/form-data

[form-data: file=@path/to/investors.csv]
```

**Описание:** Загружает CSV файл с данными приватных инвесторов для массового создания запросов на добавление.

**Формат CSV файла:**
- Первая строка должна содержать заголовки (будет пропущена)
- Обязательные колонки: имя инвестора (1-я колонка), Twitter username (2-я колонка)
- Дополнительные колонки: дополнительное имя (3-я колонка), ProductHunt username (4-я колонка), LinkedIn username (5-я колонка)

**Ответ (успех):**
```json
{
  "success": true,
  "message": "CSV file processed successfully",
  "data": {
    "created_count": 10,
    "skipped_count": 2,
    "error_count": 1,
    "errors": ["Error processing row ['Name', '']: Missing required fields in row"]
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_FILE` | Отсутствует CSV файл |
| `INVALID_FILE_TYPE` | Некорректный тип файла (не CSV) |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

### Пример использования (HTTP-клиент)

```http
@baseUrl = http://localhost:8000/f-api
@accessToken = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

### Получение списка инвесторов (сохраненные)
GET {{baseUrl}}/investors/?saved=true
Authorization: Bearer {{accessToken}}

### Получение списка инвесторов (несохраненные)
GET {{baseUrl}}/investors/?saved=false
Authorization: Bearer {{accessToken}}

### Сохранение инвесторов в избранное
POST {{baseUrl}}/investors/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "participant_ids": [123, 456]
}

### Удаление инвесторов из избранного
DELETE {{baseUrl}}/investors/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "participant_ids": [123, 456]
}

### Получение списка приватных инвесторов
GET {{baseUrl}}/investors/private/
Authorization: Bearer {{accessToken}}

### Создание запроса на добавление приватного инвестора
POST {{baseUrl}}/investors/private/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "name": "Имя инвестора",
  "twitter_headline": "twitter_username",
  "product_hunt_headline": "producthunt_username",
  "linkedin_headline": "linkedin_username"
}

### Удаление запроса на добавление приватного инвестора
DELETE {{baseUrl}}/investors/private/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "req_id": 123
}

### Загрузка CSV файла с приватными инвесторами
POST {{baseUrl}}/investors/private/csv/
Authorization: Bearer {{accessToken}}
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="investors.csv"
Content-Type: text/csv

< ./investors.csv
------WebKitFormBoundary7MA4YWxkTrZu0gW--
``` 