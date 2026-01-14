# Документация для фидов

## Фиды платформы

### Базовый URL
```
{{baseUrl}}/f-api/feeds/
```

### Эндпоинты фидов

#### 1. Получение всех сигналов
```
GET /feeds/all-signals/
Authorization: Bearer {{accessToken}}
```

**Параметры запроса:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `page` | integer | Номер страницы (по умолчанию: 1) |
| `page_size` | integer | Количество карточек на странице (по умолчанию: 20) |
| `hide_liked` | boolean | Скрыть сохраненные карточки (true/false) |
| `search` | string | Поисковый запрос |
| `min_sig` | integer | Минимальное количество сигналов (по умолчанию: 1) |
| `max_sig` | integer | Максимальное количество сигналов |
| `unique` | boolean | Только уникальные сигналы (true/false) |
| `last_week` | boolean | Только карточки за последнюю неделю (true/false) |
| `start_date` | string | Начальная дата фильтрации (формат: DD.MM.YYYY) |
| `end_date` | string | Конечная дата фильтрации (формат: DD.MM.YYYY) |

**Описание:** Возвращает список всех доступных карточек сигналов в соответствии с указанными фильтрами. Карточки сортируются по дате последнего сигнала (от новых к старым). Если указан поисковый запрос, карточки сортируются по релевантности поиска, а затем по дате последнего сигнала.

**Особенности:**
- Исключает карточки со статусом "worth_following"
- Учитывает приватность участников (показывает приватных участников только если пользователь их сохранил)
- Применяет пользовательские фильтры (категории, участники, статусы раундов, стадии)
- Исключает удаленные карточки
- При указании `hide_liked=true` исключает карточки, сохраненные в любой папке пользователя

**Ответ (успех):**
```json
{
  "success": true,
  "loadMore": true,
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
      "description": "Snowball helps content creators grow on X by writing personalized posts and replies optimized for engagement with AI - at lightning speed.",
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
    }
  ],
  "total_count": 42,
  "total_pages": 3,
  "current_page": 1
}
```

**Возможные ошибки:**
| Код ошибки | Описание |
|------------|----------|
| `AUTHENTICATION_FAILED` | Ошибка аутентификации |
| `INVALID_DATE_FORMAT` | Неверный формат даты. Используйте ДД.ММ.ГГГГ |
| `SERVER_ERROR` | Внутренняя ошибка сервера |
