

# Platform API

## Аутентификация

### Базовый URL
````language=
{{baseUrl}}/f-api/auth/
````


### Эндпоинты аутентификации

#### 1. Получение метаданных для регистрации
````language=http
GET /auth/registration-meta/
````


**Описание:** Возвращает необходимые метаданные для формы регистрации, включая доступные типы пользователей.

**Ответ:**
````language=json
{
  "success": true,
  "data": {
    "user_types": [
      {"value": "VC", "label": "Венчурный капиталист"},
      {"value": "ST", "label": "Стартап"}
    ]
  }
}
````


#### 2. Регистрация нового пользователя
````language=http
POST /auth/register/
Content-Type: application/json

{
  "email": "example@email.com",
  "password": "secure_password",
  "first_name": "Имя",
  "user_type": "VC"
}
````


**Описание:** Регистрирует нового пользователя в системе. По умолчанию аккаунт создается неактивным и требует активации.

**Ответ (успех):**
````language=json
{
  "success": true,
  "message": "Registration completed successfully. Please wait for account activation."
}
````


**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_FIELDS` | Отсутствуют обязательные поля |
| `INVALID_EMAIL` | Некорректный формат email |
| `USERNAME_EXISTS` | Пользователь с таким email уже существует |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 3. Вход пользователя
````language=http
POST /auth/login/
Content-Type: application/json

{
  "email": "example@email.com",
  "password": "secure_password"
}
````


**Описание:** Аутентифицирует пользователя и возвращает токены доступа.

**Ответ (успех):**
````language=json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
````


**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_FIELDS` | Отсутствуют обязательные поля |
| `MISSING_EMAIL` | Отсутствует поле email |
| `INVALID_EMAIL` | Некорректный формат email |
| `USER_NOT_FOUND` | Пользователь с указанным email не найден |
| `INVALID_CREDENTIALS` | Неверный пароль |
| `USER_INACTIVE` | Аккаунт пользователя не активирован |
| `DATABASE_ERROR` | Ошибка при обращении к базе данных |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 4. Проверка токена
````language=http
POST /auth/verify/
Content-Type: application/json

{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
````


**Описание:** Проверяет валидность токена. Можно передать как access-токен, так и refresh-токен.

**Ответ (успех):**
````language=json
{}
````


**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `token_not_valid` | Токен недействителен или истек срок его действия |

#### 5. Обновление токена
````language=http
POST /auth/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
````


**Описание:** Обновляет токен доступа с использованием refresh-токена.

**Ответ (успех):**
````language=json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
````


**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `token_not_valid` | Refresh-токен недействителен или истек срок его действия |

#### 6. Выход из системы
````language=http
POST /auth/logout/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
````


**Описание:** Выполняет выход пользователя из системы, инвалидируя refresh-токен.

**Ответ (успех):**
````language=json
{
  "detail": "Successfully logged out."
}
````


**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `token_not_valid` | Refresh-токен недействителен или истек срок его действия |

#### 7. Получение списка активных токенов
````language=http
GET /auth/tokens/
Authorization: Bearer {{accessToken}}
````


**Описание:** Возвращает список всех активных JWT токенов (refresh токенов) текущего пользователя, а также информацию о типе доступа и оставшихся запросах.

**Ответ (успех):**
````language=json
{
  "success": true,
  "data": {
    "tokens": [
      {
        "jti": "550e8400-e29b-41d4-a716-446655440000",
        "created_at": "2024-12-03T10:30:00Z",
        "expires_at": "2024-12-04T10:30:00Z",
        "last_used_at": null,
        "device_info": null
      }
    ],
    "tokens_count": 1,
    "tokens_available": null
  },
  "access": {
    "type": "paid",
    "is_paid": true,
    "limit": 500,
    "current_count": 150,
    "remaining": 350
  }
}
````


**Поля ответа:**

**`data.tokens`** - массив активных токенов:
- `jti` - JWT ID токена (используется для удаления)
- `created_at` - дата создания токена
- `expires_at` - дата истечения токена
- `last_used_at` - дата последнего использования (всегда null для JWT токенов)
- `device_info` - информация об устройстве (если доступна)

**`data.tokens_count`** - количество активных токенов

**`data.tokens_available`** - количество токенов, которые можно создать (null = неограниченно). Для JWT токенов (используемых фронтендом) ограничений нет.

**`access`** - информация о доступе:
- `type` - тип доступа: `"paid"` (платный) или `"free"` (бесплатный)
- `is_paid` - булево значение, является ли доступ платным
- `limit` - лимит запросов (для платных - в день, для бесплатных - всего)
- `current_count` - текущее количество использованных запросов
- `remaining` - количество оставшихся запросов

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `FEATURE_NOT_AVAILABLE` | Token management недоступен (token_blacklist не установлен) |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

### Использование токенов

После успешной аутентификации полученный токен доступа (access token) должен быть включен в заголовок Authorization для всех последующих запросов к защищенным эндпоинтам API:

````language=http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
````


Токен доступа имеет ограниченный срок действия. Когда он истекает, используйте refresh-токен для получения нового токена доступа через эндпоинт `/auth/refresh/`.

### Пример использования (HTTP-клиент)

````language=http
@baseUrl = http://localhost:8000/f-api
@email = user@example.com
@password = secure_password
@accessToken = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
@refreshToken = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

### Получение метаданных для регистрации
GET {{baseUrl}}/auth/registration-meta/

### Регистрация нового пользователя
POST {{baseUrl}}/auth/register/
Content-Type: application/json

{
  "email": "{{email}}",
  "password": "{{password}}",
  "first_name": "Имя",
  "user_type": "VC"
}

### Логин пользователя
POST {{baseUrl}}/auth/login/
Content-Type: application/json

{
  "email": "{{email}}",
  "password": "{{password}}"
}

### Проверка токена
POST {{baseUrl}}/auth/verify/
Content-Type: application/json

{
  "token": "{{accessToken}}"
}

### Обновление токена
POST {{baseUrl}}/auth/refresh/
Content-Type: application/json

{
  "refresh": "{{refreshToken}}"
}

### Выход из системы
POST {{baseUrl}}/auth/logout/
Content-Type: application/json

{
  "refresh": "{{refreshToken}}"
}
```

### Получение списка активных токенов
```http
GET {{baseUrl}}/auth/tokens/
Authorization: Bearer {{accessToken}}
```

### Создание нового токена
```http
POST {{baseUrl}}/auth/tokens/create/
Authorization: Bearer {{accessToken}}
Content-Type: application/json
```

**Примечание:** Для JWT токенов (используемых фронтендом) нет ограничений на количество. Пользователь может создать неограниченное количество токенов.

### Удаление токена
```http
DELETE {{baseUrl}}/auth/tokens/550e8400-e29b-41d4-a716-446655440000/
Authorization: Bearer {{accessToken}}
```

Или через body:
```http
DELETE {{baseUrl}}/auth/tokens/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "jti": "550e8400-e29b-41d4-a716-446655440000"
}
```

Или через refresh токен:
```http
DELETE {{baseUrl}}/auth/tokens/
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "refresh": "{{refreshToken}}"
}
````

