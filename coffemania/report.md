# Coffeemania API — Результаты проверки эндпоинтов
Дата: 2026-06-26

## Эндпоинты

| # | Endpoint | HTTP | success | Кол-во записей |
|---|----------|------|---------|----------------|
| 1 | `GET /api/Info/Dishes` | 200 | true | 8 630 блюд |
| 2 | `GET /api/Info/DishRestrictions` | 200 | true | 1 027 стоп-записей |
| 3 | `GET /api/Info/Modifiers` | 200 | true | 479 модификаторов |

Base URL: `https://relay2.coffeemania.ru:5015`

---

## 1. Dishes (`dishes.json`)
- **8 630 блюд** в ответе
- Ключевые поля: `sku`, `name`, `price`, `calories`, `fats`, `proteins`, `carbohydrates`, `weightStr`, `composition`, `siteComposition`, `allergens`, `availableInDepartments`, `extendedCategories`, `isOutdated`, `onSale`
- Фильтры из ТЗ, которые нужно применять на стороне клиента:
  - `isOnline == true` (поле отсутствует в ответе — уточнить)
  - `isDisabled == false` (поле отсутствует — уточнить)
  - `isSpecial == false` (поле отсутствует — уточнить)
  - `isAlcohol == false` (поле отсутствует — уточнить)
- Пример первой записи: `sku: "894110"`, `name: "МАНГО ТАЙСКОЕ 1Г"`, `price: 700`

## 2. DishRestrictions (`restrictions.json`)
- **1 027 записей** (блюда с ограничениями по ресторанам)
- Структура: `{ sku, departments: [id, ...] }` — перечень ресторанов где блюдо **недоступно**
- Пример: `sku: "811394"` недоступно в 22 ресторанах

## 3. Modifiers (`modifiers.json`)
- **479 модификаторов**
- Ключевые поля: `uid`, `sku`, `name`, `price`, `availableInDepartments`
- Пример: `"Классическое безлактозное молоко"`, price: 0

---

## Замечания

- Поля `how_to_cook` и `preparation_method` **отсутствуют** в ответе (как и указано в ТЗ — предоставить не могут)
- `is_active` / `is_deleted` в явном виде нет — нужно вычислять через `isOutdated` и `onSale`
- Поля фильтров (`isOnline`, `isDisabled`, `isSpecial`, `isAlcohol`) в ответе `Dishes` не обнаружены — требует уточнения у Coffeemania
- Сырые данные: `dishes.json`, `restrictions.json`, `modifiers.json`
