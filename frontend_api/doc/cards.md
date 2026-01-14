# Platform API

## Управление карточками сигналов

### Базовый URL

```
{{baseUrl}}/f-api/cards/
```

### Эндпоинты управления карточками

#### 1. Получение списка карточек

```
GET /cards/
Authorization: Bearer {{accessToken}}
```

**Параметры запроса:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `page` | integer | Номер страницы (по умолчанию: 1) |
| `page_size` | integer | Количество карточек на странице (по умолчанию: 20) |
| `type` | string | Тип карточек: saved (сохраненные), notes (с заметками), remote (удаленные) |
| `folder_key` | string/integer | ID папки или 'default' для папки по умолчанию |
| `hide_liked` | boolean | Скрыть сохраненные карточки (true/false) |
| `search` | string | Поисковый запрос |
| `min_sig` | integer | Минимальное количество сигналов (по умолчанию: 1) |
| `max_sig` | integer | Максимальное количество сигналов |
| `unique` | boolean | Только уникальные сигналы (true/false) |
| `last_week` | boolean | Только карточки за последнюю неделю (true/false) |
| `start_date` | string | Начальная дата фильтрации (формат: DD.MM.YYYY) |
| `end_date` | string | Конечная дата фильтрации (формат: DD.MM.YYYY) |

**Описание:** Возвращает список карточек сигналов в соответствии с указанными фильтрами. При указании `folder_key` возвращаются только карточки из указанной папки, отсортированные по дате добавления в папку (от новых к старым). Если указано значение `folder_key=default`, используется папка пользователя, помеченная как папка по умолчанию.

**Ответ (успех):**

```json
{
  "success": true,
  "loadMore": false,
  "cards": [
    {
      "id": 4,
      "slug": "snowball-4",
      "uuid": "59bea92e-462b-409d-9f7b-4646382cbd21",
      "name": "Notion Labs",
      "image": "http://127.0.0.1:8000/media/signalcard/snowball-4_4.png",
      "is_liked": false,
      "has_note": true,
      "stage_info": {
        "name": "Very Early",
        "slug": "very_early"
      },
      "round_status_info": {
        "key": "about_to_raise",
        "name": "About to Raise"
      },
      "created_date": "2024-05-12",
      "latest_date": "2024-11-14",
      "location": "San Francisco, CA",
      "last_round": "2024-06-15",
      "description": "Snowball helps content creators grow on X by writing personalized posts and replies optimized for engagement with AI - at lightning speed. Access all the magic directly from the X/Twitter interface with the browser extension as well.",
      "url": "https://snowball.xyz",
      "social_links": [
        {
          "name": "twitter",
          "url": "https://x.com/i/user/1899268934131691520"
        },
        {
          "name": "linkedin",
          "url": "https://www.linkedin.com/company/yadaphone/"
        }
      ],
      "categories_list": [
        {
          "id": 5,
          "name": "Тест",
          "slug": "test"
        },
        {
          "id": 6,
          "name": "__Тест",
          "slug": "test_for_test"
        }
      ],
      "participants_list": [
        {
          "name": "Michael",
          "image": null,
          "is_saved": false,
          "is_private": false
        },
        {
          "name": "Michael (M)",
          "image": "http://127.0.0.1:8000/media/participant/6producthunt19_31_XrV6KLZ.png",
          "is_saved": true,
          "is_private": true
        }
      ],
      "participants_more_count": 3,
      "participants_has_more": true
    },
    {
      "id": 6,
      "slug": "new-signal-card-slug",
      "uuid": "5687fcde-9fde-4c87-a67c-bdc4905d05cd",
      "name": "New Signal Card",
      "image_url": null,
      "is_liked": false,
      "has_note": false,
      "stage_info": {
        "name": "Unknown",
        "slug": "unknown"
      },
      "round_status_info": {
        "key": "unknown",
        "name": "Unknown"
      },
      "created_date": "2024-02-25",
      "latest_date": "2024-11-14",
      "location": null,
      "last_round": null,
      "description": "This is a new signal card.",
      "url": null,
      "social_links": [],
      "categories_list": [],
      "participants_list": [
        {
          "name": "Michael",
          "image": "http://127.0.0.1:8000/media/participant/twf3_None.jpg",
          "is_saved": true,
          "is_private": false
        }
      ],
      "participants_more_count": 0,
      "participants_has_more": false
    }
  ],
  "total_count": 2,
  "total_pages": 1,
  "current_page": 1
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `FOLDER_NOT_FOUND` | Папка не найдена |
| `DEFAULT_FOLDER_NOT_FOUND` | Папка по умолчанию не найдена |
| `INVALID_DATE_FORMAT` | Неверный формат даты |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 2. Добавление карточки в избранное

```
POST /cards/{card_id}/favorite/
Authorization: Bearer {{accessToken}}
Content-Type: application/json
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для добавления в избранное |

**Описание:** Добавляет карточку в папку избранного пользователя (папка по умолчанию).

**Ответ (успех):**

```json
{
  "success": true,
  "message": "Карточка успешно добавлена в избранное"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_CARD_ID` | ID карточки не указан |
| `ALREADY_LIKED` | Карточка уже находится в избранном |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 3. Удаление карточки из избранного

```
DELETE /cards/{card_id}/favorite/
Authorization: Bearer {{accessToken}}
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для удаления из избранного |

**Описание:** Удаляет карточку из папки избранного пользователя (папка по умолчанию).

**Ответ (успех):**

```json
{
  "success": true,
  "message": "Карточка успешно удалена из избранного"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_CARD_ID` | ID карточки не указан |
| `NOT_LIKED` | Карточка не найдена в избранном |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 4. Добавление карточки в список удаленных

```
POST /cards/{card_id}/delete/
Authorization: Bearer {{accessToken}}
Content-Type: application/json
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для добавления в список удаленных |

**Описание:** Добавляет карточку в список удаленных и удаляет из всех папок пользователя.

**Ответ (успех):**

```json
{
  "success": true,
  "message": "Карточка успешно удалена"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_CARD_ID` | ID карточки не указан |
| `ALREADY_DELETED` | Карточка уже находится в списке удаленных |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 5. Восстановление карточки из списка удаленных

```
DELETE /cards/{card_id}/delete/
Authorization: Bearer {{accessToken}}
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для восстановления из списка удаленных |

**Описание:** Восстанавливает карточку из списка удаленных.

**Ответ (успех):**

```json
{
  "success": true,
  "message": "Карточка успешно восстановлена"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_CARD_ID` | ID карточки не указан |
| `NOT_DELETED` | Карточка не найдена в списке удаленных |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 6. Создание или обновление заметки к карточке

```
POST /cards/{card_id}/note/
Authorization: Bearer {{accessToken}}
Content-Type: application/json
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для добавления заметки |

**Тело запроса:**

```json
{
  "note_text": "Текст заметки"
}
```

**Параметры запроса:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `note_text` | string | Текст заметки |

**Описание:** Создает новую или обновляет существующую заметку к карточке. Если текст заметки пустой, заметка удаляется.

**Ответ (успех при создании):**

```json
{
  "success": true,
  "message": "Заметка успешно создана"
}
```

**Ответ (успех при обновлении):**

```json
{
  "success": true,
  "message": "Заметка успешно обновлена"
}
```

**Ответ (успех при удалении):**

```json
{
  "success": true,
  "message": "Заметка успешно удалена"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_CARD_ID` | ID карточки не указан |
| `MISSING_NOTE_TEXT` | Текст заметки не указан |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 7. Удаление заметки к карточке

```
DELETE /cards/{card_id}/note/
Authorization: Bearer {{accessToken}}
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для удаления заметки |

**Описание:** Удаляет заметку к карточке.

**Ответ (успех):**

```json
{
  "success": true,
  "message": "Заметка успешно удалена"
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `MISSING_CARD_ID` | ID карточки не указан |
| `NOTE_NOT_FOUND` | Заметка не найдена |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 8. Получение заметки к карточке

```
GET /cards/{card_id}/note/
Authorization: Bearer {{accessToken}}
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для получения заметки |

**Описание:** Возвращает заметку к карточке. Если заметка не существует, поле `note_text` будет иметь значение `null`.

**Ответ (успех, заметка существует):**

```json
{
  "success": true,
  "note": {
    "card_id": 4,
    "note_text": "Текст заметки",
    "created_at": "2024-05-12T12:00:00",
    "updated_at": "2024-05-12T12:00:00"
  }
}
```

**Ответ (успех, заметка отсутствует):**

```json
{
  "success": true,
  "note": {
    "card_id": 4,
    "note_text": null,
    "created_at": null,
    "updated_at": null
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `CARD_NOT_FOUND` | Карточка не найдена |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

#### 9. Получение детальной информации о карточке

```
GET /cards/{card_id}/
GET /cards/by-slug/{slug}/
Authorization: Bearer {{accessToken}}
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `card_id` | integer | ID карточки для получения детальной информации |
| `slug` | string | Slug карточки (альтернативный способ идентификации) |

**Описание:** Возвращает детальную информацию о карточке сигнала, включая полный список участников, сигналы и пользовательские данные.

**Ответ (успех):**

```json
{
  "success": true,
  "card": {
    "ticket_status": true,
    "latest_signal_date": "2024-11-14",
    "discovered_at": "2024-08-19",
    "people": [],
    "participants": [
      {
        "sources": [
          {
            "type": "linkedin",
            "slug": "unique-tyu-14",
            "link": "https://www.linkedin.com/in/unique-tyu-14"
          }
        ],
        "associated_id": 26,
        "associated_saved": true,
        "associated_slug": "unique-tyu-14",
        "associated_about": "Описание участника",
        "associated_name": "Ytu",
        "associated_image": null,
        "associated_is_private": false,
        "associated_signal_created_at": "2024-08-19",
        "more": []
      }
    ],
    "signals": [
      {
        "sources": [
          {
            "type": "linkedin",
            "slug": "unique-tyu-14",
            "link": "https://www.linkedin.com/in/unique-tyu-14"
          }
        ],
        "associated_id": 26,
        "associated_saved": true,
        "associated_slug": "unique-tyu-14",
        "associated_about": "Описание участника",
        "associated_name": "Ytu",
        "associated_image": null,
        "associated_is_private": false,
        "associated_signal_created_at": "2024-11-14",
        "more": []
      }
    ],
    "user_data": {
      "note_text": null,
      "folders": [
        {
          "id": 1,
          "name": "Favorites",
          "is_default": true,
          "has_card": true
        },
        {
          "id": 25,
          "name": "Test",
          "is_default": false,
          "has_card": false
        }
      ]
    }
  }
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `MISSING_IDENTIFIER` | Не указан ID или slug карточки |
| `ACCESS_DENIED` | У пользователя нет доступа к этой карточке |
| `CARD_NOT_FOUND` | Карточка не найдена |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

### Публичные эндпоинты

#### 10. Публичный preview карточки

```
GET /public/{identifier}/preview/
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `identifier` | string | UUID или slug карточки |

**Описание:** Возвращает основную информацию о карточке сигнала без авторизации. Карточка должна быть помечена как публичная (`is_open=true`).

**Ответ (успех):**

```json
{
  "success": true,
  "card": {
    "id": 16694,
    "slug": "lokesh-mahala-stealth-20250821-093106",
    "uuid": "28ced737-aaae-4e59-be0c-f32021a15b40",
    "name": "Lokesh Mahala - Stealth Startup",
    "description": "Founder at Stealth Startup. Lokesh is currently leading Stealth Startup as a Founder, with prior engineering experience at Stripe and Recko, and is an IIT Roorkee alumnus.",
    "image": null,
    "url": "https://example.com/stealth-startup",
    "created_date": "2025-08-21",
    "last_round": null,
    "stage_info": {
      "name": "Seed",
      "slug": "seed"
    },
    "round_status_info": {
      "key": "raising_now",
      "name": "Raising Now"
    },
    "location": "",
    "social_links": [],
    "categories_list": [
      {
        "id": 5,
        "name": "Technology",
        "slug": "technology"
      }
    ]
  }
}
```

#### 11. Публичная детальная информация о карточке (с LinkedIn данными)

```
GET /public/{identifier}/detail/
```

**Параметры URL:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `identifier` | string | UUID или slug карточки |

**Параметры запроса:**
| Параметр | Тип | Описание | По умолчанию |
|----------|-----|----------|--------------|
| `include_signals` | boolean | Включать ли сигналы в ответ | `true` |
| `signals_limit` | integer | Ограничение количества сигналов | `5` |

**Описание:** Возвращает детальную информацию о карточке сигнала без авторизации, включая LinkedIn данные, если они доступны. Карточка должна быть помечена как публичная (`is_open=true`).

**Ответ (успех):**

```json
{
  "success": true,
  "card": {
    "id": 16694,
    "slug": "lokesh-mahala-stealth-20250821-093106",
    "uuid": "28ced737-aaae-4e59-be0c-f32021a15b40",
    "name": "Lokesh Mahala - Stealth Startup",
    "description": "Founder at Stealth Startup. Lokesh is currently leading Stealth Startup as a Founder, with prior engineering experience at Stripe and Recko, and is an IIT Roorkee alumnus.",
    "image": null,
    "url": "https://example.com/stealth-startup",
    "created_date": "2025-08-21",
    "latest_signal_date": "2025-08-21",
    "discovered_at": "2025-08-21",
    "last_round": null,
    "stage_info": {
      "name": "Seed",
      "slug": "seed"
    },
    "round_status_info": {
      "key": "raising_now",
      "name": "Raising Now"
    },
    "location": "",
    "social_links": [],
    "categories": [
      {
        "id": 5,
        "name": "Technology",
        "slug": "technology"
      }
    ],
    "tags": [
      {
        "id": 176,
        "name": "Declared Founder"
      },
      {
        "id": 177,
        "name": "Left-to-Build"
      },
      {
        "id": 178,
        "name": "ex-Stripe"
      },
      {
        "id": 179,
        "name": "IIT Roorkee"
      }
    ],
    "people": [
      {
        "id": 123,
        "name": "John Doe",
        "type": "Founder",
        "image": "https://example.com/john.jpg",
        "twitter_url": "https://twitter.com/johndoe",
        "linkedin_url": "https://linkedin.com/in/johndoe",
        "crunchbase_url": "https://crunchbase.com/person/john-doe",
        "reference_url": "https://example.com",
        "email": "john@example.com",
        "bio": "Experienced founder with multiple exits"
      }
    ],
    "signals": [
      {
        "sources": [
          {
            "type": "LinkedIn",
            "slug": "linkedin_14",
            "link": "https://www.linkedin.com/in/ACwAABZSxpUBlX5jSVBzBv-LJdwd2cSe0XG-HnY"
          }
        ],
        "linkedinData": {
          "id": 14,
          "name": "Lokesh Mahala",
          "linkedinProfileUrl": "https://www.linkedin.com/in/ACwAABZSxpUBlX5jSVBzBv-LJdwd2cSe0XG-HnY",
          "linkedinProfileImageUrl": "https://media.licdn.com/dms/image/v2/C5103AQH1iOMHHjqz9Q/profile-displayphoto-shrink_400_400/0/1585731422106?e=1758153600&v=beta&t=ISJuzAP6S9yzLm7olRm8VgYfcXruy2E2S48uNdzfK44",
          "classification": "strong_potential_founder",
          "path": "imminent_founder",
          "reasoning": "Path A (Declared Founder) is satisfied with him currently being a Founder at Stealth Startup. A Left-to-Build signal is present: he left Stripe (end date 2025-05-01) and started Stealth Startup on 2025-06-01, within 6 months, indicating readiness to build a venture. Stripe is a Tier-1 target company, strengthening the founder-target signal.",
          "tags": [
            "Declared Founder",
            "Left-to-Build",
            "ex-Stripe",
            "IIT Roorkee"
          ],
          "summary": "Lokesh is currently leading Stealth Startup as a Founder, with prior engineering experience at Stripe and Recko, and is an IIT Roorkee alumnus.",
          "experience": [
            "Founder at Stealth Startup (2025-06 to present)",
            "Software Engineer at Stripe (2022-01 to 2025-05)"
          ],
          "education": [
            "Bachelor's degree from Indian Institute of Technology, Roorkee"
          ],
          "notableAchievements": "Launched AI-driven accounts receivable capabilities at Stealth Startup",
          "oneLiner": null,
          "location": null,
          "curated": true,
          "archived": false,
          "createdAt": "2025-08-20T12:19:16.970976+00:00",
          "updatedAt": "2025-08-22T10:14:52.320940+00:00"
        },
        "linkedin_signal_created_at": "2025-08-21",
        "more": []
      },
      {
        "sources": [
          {
            "type": "linkedin",
            "slug": "unique-tyu-14",
            "link": "https://www.linkedin.com/in/unique-tyu-14"
          }
        ],
        "associated_id": 26,
        "associated_saved": false,
        "associated_slug": "unique-tyu-14",
        "associated_about": "Описание участника",
        "associated_name": "Ytu",
        "associated_image": null,
        "associated_is_private": false,
        "associated_signal_created_at": "2025-08-19",
        "more": []
      }
    ]
  }
}
```

**Структура LinkedIn данных в сигналах:**

| Поле                         | Тип     | Описание                                                                |
| ---------------------------- | ------- | ----------------------------------------------------------------------- |
| `linkedin_id`                | integer | Уникальный ID LinkedIn данных                                           |
| `linkedin_name`              | string  | Имя из LinkedIn профиля                                                 |
| `linkedin_profile_url`       | string  | URL LinkedIn профиля                                                    |
| `linkedin_profile_image_url` | string  | URL изображения профиля                                                 |
| `linkedin_classification`    | string  | Классификация: `strong_potential_founder`, `potential_founder`, `noise` |
| `linkedin_path`              | string  | Путь: `declared_founder`, `imminent_founder`                            |
| `linkedin_reasoning`         | string  | Обоснование классификации                                               |
| `linkedin_tags`              | array   | Массив тегов из LinkedIn данных                                         |
| `linkedin_signal_created_at` | string  | Дата создания сигнала (YYYY-MM-DD)                                      |

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `CARD_NOT_FOUND` | Карточка не найдена или не является публичной |
| `SERVER_ERROR` | Внутренняя ошибка сервера |

**Примеры использования:**

1. **Получение детальной информации с LinkedIn данными:**

```bash
curl "https://theveck.com:8000/f-api/public/lokesh-mahala-stealth-20250821-093106/detail/"
```

2. **Получение только основной информации без сигналов:**

```bash
curl "https://theveck.com:8000/f-api/public/lokesh-mahala-stealth-20250821-093106/detail/?include_signals=false"
```

3. **Ограничение количества сигналов:**

```bash
curl "https://theveck.com:8000/f-api/public/lokesh-mahala-stealth-20250821-093106/detail/?signals_limit=3"
```

4. **Использование UUID вместо slug:**

```bash
curl "https://theveck.com:8000/f-api/public/28ced737-aaae-4e59-be0c-f32021a15b40/detail/"
```
