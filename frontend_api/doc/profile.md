# Platform API

## Управление профилем пользователя

### Базовый URL
```
{{baseUrl}}/f-api/
```

### Эндпоинты управления профилем

#### 1. Получение данных профиля
```http
GET /profile/
Authorization: Bearer {{accessToken}}
```

**Описание:** Возвращает информацию о профиле текущего пользователя.

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "username": "username",
    "email": "example@email.com",
    "first_name": "Имя",
    "last_name": "Фамилия",
    "user_type": "PE",
    "avatar": "http://example.com/media/user_avatars/123/avatar.jpeg"
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `USER_NOT_FOUND` | Профиль пользователя не найден |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 2. Обновление профиля
```http
PUT /profile/update/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "email": "new@example.com",
  "first_name": "Новое имя",
  "last_name": "Новая фамилия",
  "user_type": "PE"
}
```

**Описание:** Обновляет информацию профиля текущего пользователя. Все поля являются опциональными.

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "username": "username",
    "email": "new@example.com",
    "first_name": "Новое имя",
    "last_name": "Новая фамилия",
    "user_type": "PE",
    "avatar": "http://example.com/media/user_avatars/123/avatar.jpeg"
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `INVALID_DATA` | Некорректные данные в запросе |
| `USER_NOT_FOUND` | Профиль пользователя не найден |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 3. Изменение пароля
```http
POST /password/change/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "current_password": "текущий_пароль",
  "new_password": "новый_пароль"
}
```

**Описание:** Изменяет пароль текущего пользователя.

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `INVALID_CURRENT_PASSWORD` | Неверный текущий пароль |
| `INVALID_PASSWORD` | Новый пароль не соответствует требованиям безопасности |
| `MISSING_FIELDS` | Отсутствуют обязательные поля |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

### Пример использования (HTTP-клиент)

```http
@baseUrl = http://localhost:8000/f-api
@accessToken = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

### Получение данных профиля
GET {{baseUrl}}/profile/
Authorization: Bearer {{accessToken}}

### Обновление профиля
PUT {{baseUrl}}/profile/update/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "email": "new@example.com",
  "first_name": "Новое имя",
  "last_name": "Новая фамилия",
  "user_type": "PE"
}

### Изменение пароля
POST {{baseUrl}}/password/change/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "current_password": "текущий_пароль",
  "new_password": "новый_пароль"
}
``` 