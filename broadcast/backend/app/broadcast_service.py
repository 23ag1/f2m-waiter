"""
Сервис рассылки: фильтрация профилей (PostgreSQL), генерация сообщений (LLM),
отправка через Telegram Bot API, логирование.
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

import httpx

from .llm_client import call_llm_chat
from . import mock_llm

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Промпты (меняешь тут — меняется поведение)
# ──────────────────────────────────────────────

FILTER_EXTRACTION_PROMPT = r"""
Ты помощник для анализа запросов администратора по рассылке сообщений пользователям.

Твоя задача: проанализировать запрос админа и выделить фильтры для отбора пользователей.

Фильтры бывают двух типов:
1. ОБЯЗАТЕЛЬНЫЕ (obvious) - те, что явно указаны в запросе администратора
2. РЕКОМЕНДУЕМЫЕ (recommended) - те, что логически следуют из контекста (например, не предлагать острое блюдо тем, кто не любит острое)

Верни строго валидный JSON без комментариев.

ПРИМЕР:

Запрос админа: Расскажи всем женщинам 22-25 лет о вводе супа Том Ям
Твой ответ:
    {
    "sex": "Женщина",
    "age_min": 22,
    "age_max": 25,
    "style": null,
    "blacklist_ingredients": ["креветки", "морепродукты", "перец чили", "кокосовое молоко", "лемонграсс"],
    "temp_state": null,
    "temp_category": null,
    "ccal": 180
    }

Допустимые значения которые ты можешь возвращать:
- sex: одно из значений из ['Женщина', 'Мужчина']
- age_min: минимальный возраст int (>=)
- age_max: максимальный возраст int (<=)
- style: одно из значений из ['Диетическое', 'Стандартное', 'Веганство', 'Вегетарианство'] (дополнение: будь аккуратнее с этим фильтром, не используй его без особой необходимости)
- blacklist_ingredients: список ТОЛЬКО характерных для этого блюда ингредиентов и типичных аллергенов — чтобы отфильтровать пользователей с соответствующей нелюбовью/аллергией.
    Включай: основной белок (говядина, курица, рыба и т.п.), специфичные специи и травы (чили, лемонграсс, кориандр), экзотические или узнаваемые компоненты (кокосовое молоко, соевый соус), типичные аллергены (морепродукты, орехи, молочные продукты, глютен — если релевантно).
    НЕ включай: общие гарниры и базовые овощи ("овощи", "салат", "гарнир", "соус", "зелень", "масло", "соль", "специи"), а также ингредиенты, которые есть в половине меню.
    Если блюдо простое (например «стейк») — оставь только основной белок: ["говядина"]. Лучше список короче, чем длиннее.
    Если не указан тип блюда (общая акция/бонусы/событие) — возвращай пустой массив [].
- temp_state: одно из значений из ["радость", "печаль", "гнев", "страх", "удивление", "отвращение", "доверие", "предвкушение", "спокойствие", "любовь", "стыд", "вина", "зависть", "гордость", "надежда", "отчаяние", "скука", "волнение", "благодарность", "одиночество", "сочувствие", "разочарование", "восхищение", "смущение", "решимость", "растерянность", "облегчение", "жалость", "восторг", "грусть"] (дополнение: будь аккуратнее с этим фильтром, не используй его без особой необходимости),
- temp_category: одно из значений из ['Гарниры', 'Салаты', 'Хинкали', 'Закуски', 'Салаты и закуски', 'Детское меню', None, 'Вок', 'Мангал', 'Хлеб', 'Корейский стритфуд', 'Горячие блюда', 'Меню от шефа', 'Паста', 'Десерты', 'Холодные закуски', 'Японская кухня', 'Выпечка', 'Завтрак', 'Поке', 'Мясо и птица', 'Чебуреки', 'Обед по-корейски', 'Дары моря', 'Напитки', 'Горячие закуски', 'Супы'] (дополнение: будь аккуратнее с этим фильтром, не используй его без особой необходимости),
- ccal: примерное число калорий int

Правила:
1) Если параметр не указан в запросе, используй null или пустой массив []
2) Верни только JSON, без текста объяснений
"""

# ──────────────────────────────────────────────
# Шаблоны промптов из папки "Промпты рассылка"
# Каждый шаблон хранит полную исходную структуру:
#   Цель → Когда использовать → Поведенческая логика →
#   Инструкция (Заголовок/Текст/CTA/Тон) → Не делать →
#   Персонализация → Примеры → общий хвост (_PROMPT_FOOTER).
#
# Запускается в generate_messages_for_users() на КАЖДОГО отфильтрованного
# пользователя как system_prompt; user_prompt = admin_request + JSON профиля.
# ──────────────────────────────────────────────

# Общий хвост для ВСЕХ шаблонов: границы персонализации, формат вывода (JSON), запрет на отказ.
# reasons — короткие теги «почему это сообщение подходит именно этому пользователю».
_PROMPT_FOOTER = """\

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
КРИТИЧЕСКИ ВАЖНО — граница персонализации
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ИСТОЧНИК ИСТИНЫ О БЛЮДЕ — ТОЛЬКО запрос администратора.
- Название блюда, его состав, способ готовки, вкус — берутся исключительно из admin_request.
- ЗАПРЕЩЕНО добавлять/убирать/менять ингредиенты на основе профиля пользователя.
- ЗАПРЕЩЕНО переименовывать блюдо.
  «стейк» ≠ «сырный стейк», ≠ «острый стейк», ≠ «стейк с грибами»
  «суп» ≠ «куриный суп», ≠ «острый суп»
  «пицца» ≠ «пицца с ананасом»
- Если prefer пользователя = «Сыр», а админ про стейк — это НЕ значит, что стейк сырный.
  Значит: этот человек в принципе любит насыщенный вкус, к нему можно обращаться соответствующим тоном.

ДЛЯ ЧЕГО НУЖЕН ПРОФИЛЬ (prefer / hate / style / mood / experiments):
- Выбрать ТОНАЛЬНОСТЬ обращения (спокойный/дерзкий/тёплый/рациональный)
- Выбрать ЭМОЦИОНАЛЬНУЮ ЗАЦЕПКУ (что именно зацепит этого человека в этом блюде)
- Выбрать МОТИВАЦИЮ (что подтолкнёт купить: срочность / любопытство / ностальгия)
- НО НЕ описание продукта. Продукт — неизменен, он уже есть в меню ровно таким.

Плохо: «Сырный стейк — для любителей сыра, спеши попробовать!»
        (выдумали новое блюдо, ввели в заблуждение — в меню такого нет)

Хорошо: «Новый стейк — сочный, насыщенный, такой как ты ценишь. Попробуй.»
        (то же блюдо, подача под человека, любящего насыщенные вкусы)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Формат вывода — ТОЛЬКО валидный JSON-объект, без Markdown-обёрток:
{
  "text": "<заголовок на первой строке, затем перенос и текст push-уведомления>",
  "reasons": ["<1-3 слова>", "<1-3 слова>"]
}

Поле `text`:
- Заголовок + текст push-уведомления (лимиты по знакам — как выше).
- Без кавычек, без Markdown, без пояснений.

Поле `reasons` — 1–3 очень коротких объяснения (1–3 слова каждое), почему это сообщение подходит ИМЕННО
этому пользователю, на основе его полей prefer / hate / style / mood / experiments.
Примеры: "любит насыщенный вкус", "готов к экспериментам", "стиль стандартный", "настрой радостный".
Если данных в профиле мало — допустимо вернуть 1 общую причину или пустой массив.

Отбор получателей уже сделан ДО тебя детерминированным кодом. Всегда возвращай полноценный JSON.
Никогда не возвращай "-", "—", пустую строку или отказ в поле `text` — это баг."""


MESSAGE_GENERATION_PROMPT = r"""Ты помощник, который генерирует персональное сообщение пользователю.

Входные данные (в user-prompt):
1) Запрос администратора — тема сообщения
2) Профиль пользователя из CRM (JSON)

Задача:
Сгенерировать короткое, дружелюбное, персональное сообщение,
подходящее для push-уведомления или чата.
""" + _PROMPT_FOOTER


PROMPT_TEMPLATES: Dict[str, str] = {
    "standard": MESSAGE_GENERATION_PROMPT,

    "geo": """Ты — AI-агент по гео-триггерным push-уведомлениям.

Цель:
Привести пользователя в заведение здесь и сейчас.

Когда использовать:
- пользователь рядом
- проходит мимо
- находится в районе

Поведенческая логика:
- триггер: «ты рядом — зайди»
- минимальное время на решение

Инструкция:

Заголовок:
- ≤ 40 символов
- ощущение «прямо сейчас»

Текст:
- ≤ 120 символов
- почему стоит зайти именно сейчас

CTA:
- обязателен
- «Зайди», «Загляни сейчас»

Тон:
- быстрый, простой, без сложных конструкций

Не делать:
- длинные объяснения
- абстрактные формулировки

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Учитывай его привычки (например: кофе утром, ужин вечером).

Удачные примеры (стиль, не копировать):
- «🌊Каспийка: Погода-то какая!» / «Время прогуляться за заказом. С собой скидка 20% до конца лета!»
- ««Тануки» рядом!» / «Домодедово, заходите в гости в новый ресторан и заказывайте быструю доставку»
- «Загляни в магазин рядом!» / «Он совсем рядом.»""" + _PROMPT_FOOTER,

    "clickbait": """Ты — AI-агент по созданию кликбейтных push-уведомлений.

Цель:
Максимально увеличить открываемость push.

Когда использовать:
- нужно резко повысить open rate
- усиление других типов рассылок

Поведенческая логика:
- триггер: интрига / недосказанность / провокация

Инструкция:

Заголовок:
- ≤ 40 символов
- вызывает вопрос или эмоцию
- не раскрывает суть полностью

Текст:
- ≤ 120 символов
- даёт частичное объяснение
- сохраняет интерес

CTA:
- может отсутствовать

Тон:
- дерзкий, провокационный, допускается игра на грани

Не делать:
- полный ответ в заголовке
- обман (ожидание должно оправдаться)

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt. Интрига должна быть релевантна его интересам.

Удачные примеры (стиль, не копировать):
- «‼️Важная информация‼️» / «Если пропадёт интернет, ищи нас по запаху картошечки! Тут всё стабильно»
- «📞 (1) Пропущенный от МО...» / «Ты не ответил, а мы хотели привезти роллы!»
- «Бывший» / «Есть разговор. Мне тут по ошибке твой промокод прислали. Забери, а то сгорит»
- «За вами долг» / «На новом выпуске не хватает просмотра»""" + _PROMPT_FOOTER,

    "new_items": """Ты — AI-агент по генерации push-уведомлений о новинках в заведениях, кафе, ресторанах, барах.

Цель:
Вызвать интерес и желание попробовать новое.

Когда использовать:
- новые блюда
- обновление меню
- сезонные предложения

Поведенческая логика:
- триггер: любопытство
- вторично: ощущение «хочу быть первым»

Инструкция:

Заголовок:
- ≤ 40 символов
- интрига или образ
- не раскрывать всё сразу

Текст:
- ≤ 120 символов
- кратко раскрывает новинку
- можно через эмоцию или вкус

CTA:
- опционален (мягкий)
- «Попробуй», «Оцени», «Загляни»

Тон:
- аппетитный, живой, допускается креатив и игра слов

Не делать:
- сухое описание блюда
- перегруз деталями

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Подстрой новинку под его вкусы или привычки.

Удачные примеры (стиль, не копировать):
- «Черным-черно» / «Это мы всмотрелись в новые ризотто и пасту с чернилами каракатицы. Попробуешь?»
- «Пшшшшшшш» / «Кто-то открыл новую колу. А это могли бы быть вы — хотите заказать?»
- «Привет, сладкая 🍓» / «Это мы к клубнике в шоколаде обращаемся! Попробуйте — тоже влюбитесь»
- «Борщ» / «Возвращение легенды»""" + _PROMPT_FOOTER,

    "loyalty": """Ты — AI-агент по push-уведомлениям про бонусы и лояльность.

Цель:
Увеличить возвраты клиента через бонусы, баллы и накопления.

Когда использовать:
- начисление бонусов
- напоминание о балансе
- сгорание баллов

Поведенческая логика:
- триггер: «у тебя уже есть ценность»
- усиление: страх потери

Инструкция:

Заголовок:
- ≤ 40 символов
- акцент на «твои бонусы»

Текст:
- ≤ 120 символов
- что есть и что с этим можно сделать

CTA:
- желателен
- «Потрать», «Используй»

Тон:
- рациональный + лёгкая эмоция

Не делать:
- сложные объяснения механик

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Учитывай его активность и бонусное поведение.

Удачные примеры (стиль, не копировать):
- «Вы получили 92 бонуса!» / «А могли бы 184! Узнайте, как 🤔»
- «Я календарь переверну 📆» / «А ваши 1 452 бонуса сгорают в костре рябин»
- «Ничего себе!» / «Вы накопили 30 бонусов — достаточно, чтобы получить пиццу со скидкой»
- «Помнишь про бонусы? ❤️» / «Ещё есть время их использовать»""" + _PROMPT_FOOTER,

    "reactivation": """Ты — AI-агент по генерации push-уведомлений для заведений (рестораны, кафе, бары).

Цель:
Вернуть пользователя, который давно не взаимодействовал с заведением. Сообщение должно вызвать ощущение, что про него помнят и его ждут.

Когда использовать:
- пользователь не посещал заведение длительное время
- снижение активности
- необходимость «разогреть» базу

Поведенческая логика:
- триггер: ностальгия + персональное внимание
- вторичный триггер: FOMO или лёгкая выгода
- избегать давления → мягкое вовлечение

Инструкция:

Заголовок:
- ≤ 40 символов, ≤ 7 слов
- ощущение личного обращения
- избегать обезличенных формулировок («клиент», «пользователь»)

Текст:
- ≤ 120 символов
- объясняет, почему стоит вернуться
- допускается намёк на прошлый опыт пользователя

CTA:
- обязателен
- мягкий: «Загляни», «Ждём тебя», «Возвращайся»

Тон:
- дружелюбный, «живой человек», не реклама
- можно лёгкий юмор или интрига

Не делать:
- агрессивные продажи
- длинные описания
- формальные конструкции

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Опирайся на его поведение, интересы или прошлые визиты.

Удачные примеры (стиль, не копировать):
- «Давно не виделись 👋» / «Расскажешь, почему больше не заходишь?»
- «Пора поесть» / «Это всё, что мы хотели сказать»
- «Моральная поддержка» / «Если нужно улучшить настрой, еда всегда готова приехать на помощь»
- «Пятницу знаете?» / «Это мы придумали, чтобы заказывать суши на ужин без угрызений совести ❤️»
- «Дождь в конце августа ☔» / «Повод заказать доставку из «Кофемании»»""" + _PROMPT_FOOTER,

    "situational": """Ты — AI-агент по ситуативным push-уведомлениям.

Цель:
Попасть в контекст текущей ситуации пользователя и вызвать отклик.

Когда использовать:
- погода
- время дня
- день недели
- инфоповод

Поведенческая логика:
- триггер: «это сейчас про меня»
- эффект узнавания

Инструкция:

Заголовок:
- ≤ 40 символов
- отражает ситуацию

Текст:
- ≤ 120 символов
- связывает ситуацию с предложением

CTA:
- опционален

Тон:
- живой, наблюдательный, допускается юмор

Не делать:
- оторванные от реальности сообщения

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Свяжи ситуацию с его образом жизни.

Удачные примеры (стиль, не копировать):
- «Если поздно легли» / «Поспите подольше, а мы привезём комбо на завтрак 🥞»
- «Проверьте пуховик» / «Если найдёте деньги, вот способ их потратить — закажите еду»
- «Холодный пуш» / «Потому что замёрз. Если вы тоже — закажите еду, привезут горячей»
- «Дождь в конце августа ☔» / «Повод заказать доставку»""" + _PROMPT_FOOTER,

    "discounts": """Ты — AI-агент по генерации продающих push-уведомлений.

Цель:
Стимулировать пользователя воспользоваться предложением прямо сейчас.

Когда использовать:
- акции
- скидки
- спецпредложения
- промокоды

Поведенческая логика:
- триггер: выгода + срочность (FOMO)
- пользователь должен почувствовать, что «теряет», если не откроет

Инструкция:

Заголовок:
- ≤ 40 символов, ≤ 6 слов
- сразу транслирует выгоду или ограничение
- можно цифры, проценты, суммы

Текст:
- ≤ 120 символов
- чёткие условия (что, сколько, до какого момента)
- без лишнего описания

CTA:
- обязателен
- прямой: «Успей», «Забирай», «Применяй»

Тон:
- энергичный, продающий, допускается лёгкий кликбейт

Не делать:
- размытые формулировки («выгодное предложение»)
- отсутствие конкретики

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Адаптируй выгоду под его предпочтения.

Удачные примеры (стиль, не копировать):
- «Это скидка 500 ₽» / «Вы знаете, что с ней делать»
- «Вам скидка 15%» / «Без объяснения причин»
- «Этот пуш удалён» / «Модераторами за слишком привлекательное предложение — до 30% по промокоду АПРЕЛЬ»
- «🗓️У тебя сегодня встреча» / «С красотой: самовывоз от 2500₽ и +500 бонусов»""" + _PROMPT_FOOTER,

    "events": """Ты — AI-агент по генерации push-уведомлений для событий.

Цель:
Сделать заведение выбором пользователя для праздника или события.

Когда использовать:
- праздники
- вечеринки
- специальные даты

Поведенческая логика:
- триггер: эмоция + сценарий («как проведёшь день?»)
- усиление через FOMO

Инструкция:

Заголовок:
- ≤ 40 символов
- отражает событие или настроение

Текст:
- ≤ 120 символов
- что будет происходить
- чем это лучше альтернатив

CTA:
- обязателен
- «Бронируй», «Приходи», «Отмечай»

Тон:
- эмоциональный, праздничный, допускаются отсылки и игра слов

Не делать:
- нейтральные формулировки
- отсутствие повода

Персонализация:
Профиль пользователя из CRM передаётся в user-prompt.
Учти его стиль отдыха и предпочтения.

Удачные примеры (стиль, не копировать):
- «Я календарь переверну 📆» / «А ваши бонусы сгорают в костре рябин»
- «К чёрту носки!» / «Лучше закажи ...» (23 февраля)
- «С нас бесплатный отель на 14 февраля» / «С вас — кольцо и предложение. Она точно скажет ДА!»
- «🥞 Облинились?» / «Если нет, давайте испечём главное блюдо Масленицы по рецепту»""" + _PROMPT_FOOTER,
}

# Человекочитаемые названия для фронта
PROMPT_TEMPLATE_LABELS: Dict[str, str] = {
    "standard": "Стандартный",
    "geo": "Гео",
    "clickbait": "Кликбейт",
    "new_items": "Новинки",
    "loyalty": "Программа лояльности",
    "reactivation": "Реактивация",
    "situational": "Ситуативные",
    "discounts": "Скидки, акции",
    "events": "События, праздники",
}


def get_message_prompt(template_key: str) -> str:
    """Возвращает промпт по ключу шаблона."""
    return PROMPT_TEMPLATES.get(template_key, MESSAGE_GENERATION_PROMPT)


# ──────────────────────────────────────────────
# 1. Извлечение фильтров из запроса админа (LLM)
# ──────────────────────────────────────────────

def extract_filters(admin_request: str, model: str) -> dict:
    if mock_llm.is_enabled():
        logger.info("MOCK_LLM активен → используется mock_extract_filters")
        return mock_llm.mock_extract_filters(admin_request)

    raw = call_llm_chat(
        model_provider=model,
        system_prompt=FILTER_EXTRACTION_PROMPT,
        user_prompt=admin_request,
        response_format="json_object",
    )
    return json.loads(raw)


# ──────────────────────────────────────────────
# 2. Фильтрация профилей в PostgreSQL
# ──────────────────────────────────────────────

# Маппинг диапазонов возрастов из profile.age в числа
_AGE_RANGES = {
    "до 18": (0, 17),
    "18-25": (18, 25),
    "26-35": (26, 35),
    "36-45": (36, 45),
    "46-55": (46, 55),
    "56+":   (56, 120),
}


def _age_range_matches(age_str: Optional[str], age_min: Optional[int], age_max: Optional[int]) -> bool:
    """Проверяет, попадает ли диапазон из БД в запрошенный диапазон возрастов."""
    if not age_str or age_str.strip().lower() in ("", "пусто", "none"):
        return True  # Пустой возраст — не фильтруем

    low, high = _AGE_RANGES.get(age_str.strip(), (None, None))
    if low is None:
        # Пробуем распарсить как число
        try:
            age_num = int(re.sub(r'\D', '', age_str))
            low = high = age_num
        except (ValueError, TypeError):
            return True  # Непарсируемое значение — пропускаем

    if age_min is not None and high < age_min:
        return False
    if age_max is not None and low > age_max:
        return False
    return True


def _sex_matches(db_sex: Optional[str], filter_sex: Optional[str]) -> bool:
    """Нормализованное сравнение пола."""
    if not filter_sex:
        return True
    if not db_sex or db_sex.strip().lower() in ("", "пусто", "none"):
        return True  # Пустое поле — не фильтруем

    norm = db_sex.strip().lower()
    f_norm = filter_sex.strip().lower()

    # "мужской" → "мужчина", "женский" → "женщина"
    male_variants = {"мужчина", "мужской", "м", "male"}
    female_variants = {"женщина", "женский", "ж", "female"}

    if f_norm in male_variants:
        return norm in male_variants
    if f_norm in female_variants:
        return norm in female_variants
    return norm == f_norm


def _blacklist_intersects(user_hate: Optional[str], filter_ingredients: Optional[List[str]]) -> bool:
    """True если у пользователя в blacklist есть хоть один из ингредиентов блюда."""
    if not filter_ingredients or not user_hate:
        return False
    if user_hate.strip().lower() in ("пусто", "none", ""):
        return False

    user_items = {x.strip().lower() for x in user_hate.split(",") if x.strip()}
    filter_items = {x.strip().lower() for x in filter_ingredients}
    return bool(user_items & filter_items)


def count_all_profiles(db) -> int:
    """Общее количество строк в таблице profile."""
    cursor = db.connection.execute("SELECT COUNT(*) AS cnt FROM profile")
    row = cursor.fetchone()
    if row is None:
        return 0
    return int(row["cnt"])


_LAST_VISIT_SQL = {
    # бакет: SQL-условие на last_visit
    "week":    "oh.last_visit >= NOW() - INTERVAL '7 days'",
    "month":   "oh.last_visit <  NOW() - INTERVAL '7 days'  AND oh.last_visit >= NOW() - INTERVAL '30 days'",
    "3months": "oh.last_visit <  NOW() - INTERVAL '30 days' AND oh.last_visit >= NOW() - INTERVAL '90 days'",
    "earlier": "oh.last_visit IS NULL OR oh.last_visit < NOW() - INTERVAL '90 days'",
}


def filter_profiles_pg(db, filters: dict) -> List[Dict[str, Any]]:
    """
    Фильтрует профили из таблицы profile (PostgreSQL).
    SQL для базовых фильтров + Python для возраста и blacklist.
    Опционально LEFT JOIN orders_history для фильтра по last_visit.
    """
    conditions = []
    params: list = []

    # style
    style = filters.get("style")
    if style:
        conditions.append(
            "(p.style IS NULL OR p.style = '' OR LOWER(p.style) = LOWER(%s))"
        )
        params.append(style)

    # mood
    mood = filters.get("temp_state")
    if mood:
        conditions.append(
            "(p.mood IS NULL OR p.mood = '' OR LOWER(p.mood) = LOWER(%s))"
        )
        params.append(mood)

    # last_visit (только если задан)
    last_visit = filters.get("last_visit")
    if last_visit in _LAST_VISIT_SQL:
        conditions.append(f"({_LAST_VISIT_SQL[last_visit]})")

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = (
        "SELECT p.user_id, p.fio, p.age, p.sex, p.style, p.kcal, p.prefer, p.hate, p.mood, "
        "       p.experiments, "
        "       oh.last_visit "
        "FROM profile p "
        "LEFT JOIN ( "
        "    SELECT user_id, MAX(created_at) AS last_visit "
        "    FROM orders_history "
        "    GROUP BY user_id "
        ") oh ON oh.user_id = p.user_id "
        f"WHERE {where}"
    )

    cursor = db.connection.execute(sql, tuple(params))
    rows = cursor.fetchall()

    # Пост-фильтрация в Python (возраст хранится как диапазон, blacklist)
    age_min = filters.get("age_min")
    age_max = filters.get("age_max")
    filter_sex = filters.get("sex")
    bl_ingredients = filters.get("blacklist_ingredients")

    results = []
    for row in rows:
        row_dict = {k: row[k] for k in row.keys()} if hasattr(row, 'keys') else dict(row)

        # Скипаем пустой пол/возраст ТОЛЬКО если активен соответствующий фильтр
        raw_sex = (row_dict.get("sex") or "").strip().lower()
        raw_age = (row_dict.get("age") or "").strip().lower()
        sex_empty = (not raw_sex or raw_sex in ("пусто", "none"))
        age_empty = (not raw_age or raw_age in ("пусто", "none"))

        if filter_sex and sex_empty:
            continue
        if (age_min is not None or age_max is not None) and age_empty:
            continue

        if not _age_range_matches(row_dict.get("age"), age_min, age_max):
            continue
        if not _sex_matches(row_dict.get("sex"), filter_sex):
            continue
        if _blacklist_intersects(row_dict.get("hate"), bl_ingredients):
            continue

        results.append(row_dict)

    logger.info(f"Фильтрация: {len(rows)} → {len(results)} профилей")
    return results


# ──────────────────────────────────────────────
# 3. Генерация персональных сообщений (LLM)
# ──────────────────────────────────────────────

_REFUSAL_MARKERS = {"-", "--", "---", "—", "–", "−"}
_STOP_WORDS = {
    "про", "для", "как", "где", "когда", "что", "это", "наш", "наша",
    "новый", "новая", "новое", "меню", "блюдо", "акция", "скидка",
    "сегодня", "завтра", "всем", "всех", "уже", "только",
}


def _tokenize_food(text: str) -> List[str]:
    """Вытаскивает значимые слова из admin_request для мэтча с prefer."""
    words = re.findall(r"[а-яё]{4,}", (text or "").lower())
    return [w for w in words if w not in _STOP_WORDS]


def compute_deterministic_reasons(profile: dict, admin_request: str) -> List[str]:
    """Собирает 0-4 тега из полей профиля, детерминированно."""
    tags: List[str] = []

    def _clean(s):
        return (s or "").strip()

    def _meaningful(s: str) -> bool:
        v = _clean(s).lower()
        return bool(v) and v not in ("пусто", "none", "null", "-")

    prefer = _clean(profile.get("prefer")).lower()
    if _meaningful(prefer):
        for kw in _tokenize_food(admin_request):
            if kw in prefer or (len(kw) > 5 and kw[:5] in prefer):
                tags.append(f"любит: {kw}")
                break

    exp = _clean(profile.get("experiments")).lower()
    if "эксперимент" in exp:
        tags.append("готов пробовать")

    style = _clean(profile.get("style"))
    if _meaningful(style):
        tags.append(f"стиль: {style.lower()}")

    mood = _clean(profile.get("mood"))
    if _meaningful(mood):
        tags.append(f"настрой: {mood.lower()}")

    return tags[:4]


def _parse_llm_message_payload(raw: str) -> Tuple[str, List[str]]:
    """Парсит JSON-ответ LLM формата {text, reasons}. Падение → fallback на сырой текст."""
    if not raw:
        return "", []
    raw = raw.strip()

    # Снять возможные markdown-обёртки ```json … ```
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            text = str(data.get("text", "")).strip()
            reasons_raw = data.get("reasons") or []
            if isinstance(reasons_raw, list):
                reasons = [str(r).strip() for r in reasons_raw if isinstance(r, (str, int, float))]
                reasons = [r for r in reasons if r and r.lower() not in ("пусто", "none")]
            else:
                reasons = []
            return text, reasons[:3]
    except Exception:
        pass

    # Не распарсили — вернём как есть, reasons пусто
    return raw, []


def _merge_reasons(det_tags: List[str], llm_tags: List[str], cap: int = 3) -> List[str]:
    """Мерджит детерминированные + LLM теги, убирает дубликаты (регистронезависимо)."""
    seen = set()
    out: List[str] = []
    for t in (det_tags or []) + (llm_tags or []):
        key = t.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(t.strip())
        if len(out) >= cap:
            break
    return out


def generate_message_for_profile(
    admin_request: str,
    profile: Dict[str, Any],
    model: str,
    template_key: str = "standard",
) -> Optional[Dict[str, Any]]:
    """LLM-вызов на один профиль → dict или None если LLM отказала/упала."""
    if mock_llm.is_enabled():
        try:
            payload = mock_llm.mock_generate_message(admin_request, profile)
        except Exception as e:
            logger.warning(f"MOCK_LLM ошибка для user_id={profile.get('user_id')}: {e}")
            return None
        text = (payload.get("text") or "").strip()
        if not text or len(text) < 5:
            return None
        det_reasons = compute_deterministic_reasons(profile, admin_request)
        # mock-LLM reasons первыми — они более содержательные чем детерминированные
        reasons = _merge_reasons(payload.get("reasons") or [], det_reasons, cap=3)
        return {
            "user_id": profile["user_id"],
            "fio": profile.get("fio"),
            "age": profile.get("age"),
            "sex": profile.get("sex"),
            "message": text,
            "reasons": reasons,
        }

    prompt = get_message_prompt(template_key)
    try:
        raw = call_llm_chat(
            model_provider=model,
            system_prompt=prompt,
            user_prompt=(
                f"Запрос администратора:\n{admin_request}\n\n"
                f"Профиль пользователя:\n{json.dumps(profile, ensure_ascii=False, default=str)}"
            ),
            response_format="json_object",
        )
    except Exception as e:
        logger.warning(f"LLM ошибка для user_id={profile.get('user_id')}: {e}")
        return None

    text, llm_reasons = _parse_llm_message_payload(raw)
    stripped = text.strip().strip('"').strip("'").strip()
    if not stripped or stripped in _REFUSAL_MARKERS or len(stripped) < 5:
        logger.info(f"LLM вернула отказ/слишком коротко для user_id={profile.get('user_id')}: {raw!r}")
        return None

    det_reasons = compute_deterministic_reasons(profile, admin_request)
    reasons = _merge_reasons(det_reasons, llm_reasons, cap=3)

    return {
        "user_id": profile["user_id"],
        "fio": profile.get("fio"),
        "age": profile.get("age"),
        "sex": profile.get("sex"),
        "message": stripped,
        "reasons": reasons,
    }


def generate_messages_for_users(
    admin_request: str,
    profiles: List[Dict[str, Any]],
    model: str,
    template_key: str = "standard",
) -> List[Dict[str, Any]]:
    """Батч-генерация. Используется старым /preview эндпоинтом."""
    out = []
    for profile in profiles:
        m = generate_message_for_profile(admin_request, profile, model, template_key)
        if m is not None:
            out.append(m)
    return out


# ──────────────────────────────────────────────
# 4. Отправка через Telegram Bot API
# ──────────────────────────────────────────────

async def send_telegram_message(
    client: httpx.AsyncClient,
    bot_token: str,
    user_id: int,
    text: str,
) -> Tuple[bool, Optional[str]]:
    """Отправляет сообщение одному пользователю. Возвращает (ok, error)."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = await client.post(url, json={
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return True, None
        return False, data.get("description", "Unknown error")
    except Exception as e:
        return False, str(e)


# ──────────────────────────────────────────────
# 5. Логирование рассылок в PostgreSQL
# ──────────────────────────────────────────────

def ensure_broadcast_log_table(db):
    """Создаёт таблицу broadcast_log если не существует."""
    sql = """
    CREATE TABLE IF NOT EXISTS broadcast_log (
        id SERIAL PRIMARY KEY,
        admin_request TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT 'bothub',
        filters JSONB DEFAULT '{}',
        recipients_count INTEGER DEFAULT 0,
        sent_count INTEGER DEFAULT 0,
        skipped_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """
    db.connection.execute(sql)


def log_broadcast(
    db,
    admin_request: str,
    model: str,
    filters: dict,
    recipients_count: int,
    sent_count: int,
    skipped_count: int,
):
    ensure_broadcast_log_table(db)
    sql = """
    INSERT INTO broadcast_log (admin_request, model, filters, recipients_count, sent_count, skipped_count)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    db.connection.execute(sql, (
        admin_request,
        model,
        json.dumps(filters, ensure_ascii=False),
        recipients_count,
        sent_count,
        skipped_count,
    ))


def get_broadcast_history(db, limit: int = 50) -> List[dict]:
    ensure_broadcast_log_table(db)
    sql = "SELECT * FROM broadcast_log ORDER BY created_at DESC LIMIT %s"
    cursor = db.connection.execute(sql, (limit,))
    rows = cursor.fetchall()
    return [{k: row[k] for k in row.keys()} if hasattr(row, 'keys') else dict(row) for row in rows]
