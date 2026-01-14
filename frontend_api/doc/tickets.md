# Platform API

## Управление запросами на контакт (тикетами)

### Базовый URL
```
{{baseUrl}}/f-api/
```

### Эндпоинты управления тикетами

#### 1. Создание запроса на контакт
```http
POST /tickets/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "card_id": 123
}
```

**Описание:** Создает новый запрос на контакт для указанной карточки сигнала.

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Contact request sent successfully."
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_CARD_ID` | Отсутствует ID карточки |
| `CARD_NOT_FOUND` | Указанная карточка сигнала не найдена |
| `DUPLICATE_REQUEST` | Запрос на контакт уже был отправлен |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 2. Получение списка запросов на контакт
```http
GET /tickets/
Authorization: Bearer {{accessToken}}
```

**Описание:** Возвращает список всех запросов на контакт текущего пользователя.

**Ответ (успех):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "signal_card_name": "Название карточки сигнала",
      "signal_card_image": "http://example.com/media/signal_cards/image.jpg",
      "is_processed": false,
      "created_at": "2023-01-01T12:00:00Z",
      "response_text": null
    },
    {
      "id": 2,
      "signal_card_name": "Другая карточка сигнала",
      "signal_card_image": "http://example.com/media/signal_cards/other_image.jpg",
      "is_processed": true,
      "created_at": "2023-01-02T14:30:00Z",
      "response_text": "Ответ на запрос контакта"
    }
  ]
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 3. Отмена запроса на контакт
```http
DELETE /tickets/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "ticket_id": 1
}
```

**Описание:** Отменяет (удаляет) запрос на контакт пользователя.

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Contact request cancelled successfully."
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_TICKET_ID` | Отсутствует ID запроса |
| `TICKET_NOT_FOUND` | Запрос не найден или не принадлежит пользователю |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

### Пример использования (HTTP-клиент)

```http
@baseUrl = http://localhost:8000/f-api
@accessToken = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

### Создание запроса на контакт
POST {{baseUrl}}/tickets/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "card_id": 123
}

### Получение списка запросов на контакт
GET {{baseUrl}}/tickets/
Authorization: Bearer {{accessToken}}

### Отмена запроса на контакт
DELETE {{baseUrl}}/tickets/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "ticket_id": 1
}
``` 