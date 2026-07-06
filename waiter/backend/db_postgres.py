import psycopg2
from psycopg2.extras import DictCursor
from psycopg2 import pool
import threading

import datetime
import json
import time
import re
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class CaseInsensitiveRow:
    """
    Эмуляция sqlite3.Row (доступ по индексу и имени), с поддержкой нечувствительности к регистру.
    """
    def __init__(self, row):
        self._row = row
        # keys() у DictRow возвращает список ключей
        self._lower_keys = {k.lower(): k for k in row.keys()}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._row[key]
        if isinstance(key, str):
            key_lower = key.lower()
            if key_lower in self._lower_keys:
                real_key = self._lower_keys[key_lower]
                return self._row[real_key]
        return self._row[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __len__(self):
        return len(self._row)
        
    def keys(self):
        return self._row.keys()

    def __iter__(self):
        return iter(self._row)

class PostgresCursorWrapper:
    """Обертка над курсором psycopg2 для эмуляции поведения sqlite3 cursor"""
    def __init__(self, original_cursor):
        self.cursor = original_cursor

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, query, params=()):
        try:
            # Замена ? на %s
            query = query.replace('?', '%s')
            self.cursor.execute(query, params)
            return self
        except Exception as e:
            # print(f"SQL Error: {e}")
            raise e

    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows:
            return []
        return [CaseInsensitiveRow(row) for row in rows]

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return CaseInsensitiveRow(row)
    
    def close(self):
        self.cursor.close()

class PostgresConnectionAdapter:
    """
    Адаптер соединения с пулом подключений для многопоточной среды.
    Использует ThreadedConnectionPool для безопасного параллельного доступа.
    """
    _local = threading.local()  # Thread-local storage для хранения текущего соединения
    
    def __init__(self, host, port, user, password, dbname, minconn=5, maxconn=50):
        self.dsn = f"host={host} port={port} user={user} password={password} dbname={dbname}"
        self._pool = pool.ThreadedConnectionPool(
            minconn, maxconn,
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            cursor_factory=DictCursor
        )
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._dbname = dbname
    
    def _get_conn(self):
        """Получить соединение из пула для текущего потока"""
        if not hasattr(self._local, 'conn') or self._local.conn is None or self._local.conn.closed:
            self._local.conn = self._pool.getconn()
            self._local.conn.autocommit = True
        return self._local.conn
    
    def _put_conn(self, conn=None):
        """Вернуть соединение в пул"""
        c = conn or getattr(self._local, 'conn', None)
        if c is not None:
            try:
                self._pool.putconn(c)
            except Exception:
                pass
            self._local.conn = None

    def cursor(self):
        """Возвращает новый курсор из пула соединений"""
        return PostgresCursorWrapper(self._get_conn().cursor())

    def execute(self, query, params=()):
        """Выполняет запрос с использованием нового курсора"""
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        """Фиксирует транзакцию в текущем соединении потока"""
        conn = getattr(self._local, 'conn', None)
        if conn:
            conn.commit()

    def close(self):
        """Закрывает все соединения в пуле"""
        self._pool.closeall()

    def __enter__(self):
        # Получаем соединение из пула при входе в контекст
        self._get_conn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = getattr(self._local, 'conn', None)
        if conn:
            if exc_type:
                conn.rollback()
            else:
                conn.commit()
            # НЕ возвращаем в пул здесь — соединение будет переиспользовано в том же потоке


def normalize_phone(phone: str) -> str:
    """
    Нормализация номера телефона: извлекает все цифры и берет последние 10 символов.
    Это позволяет обрабатывать номера в любом формате: +7(985)0199996, 89850199996, +7 985 019-99-96 и т.д.
    """
    if not phone:
        return ""
    # Извлекаем все цифры из номера
    digits_only = re.sub(r'\D', '', str(phone))
    # Берем последние 10 цифр (российский номер без кода страны)
    if len(digits_only) >= 10:
        return digits_only[-10:]
    # Если цифр меньше 10, возвращаем как есть
    return digits_only


class Database:
    def __init__(self, db_file=None):
        # db_file игнорируем, берем из env
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = os.getenv("POSTGRES_PORT", "5432")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD", "postgres")
        self.dbname = os.getenv("POSTGRES_DB", "food2mood")
        
        self._connection = None
        self._thread_local = threading.local()
        
        # Пытаемся подключиться сразу, но не падаем если не вышло
        self._connect(silent=False)

        # Миграция: добавляем колонку partner_id если её нет
        self._ensure_partner_id_column()

        # Список разрешенных администраторов
        self.allowed_admins = [1456241115]

    def _ensure_partner_id_column(self):
        """Добавляет колонку partner_id в Profile, если её ещё нет."""
        if self._connection is None:
            return
        try:
            self.cursor.execute(
                "ALTER TABLE Profile ADD COLUMN IF NOT EXISTS partner_id TEXT"
            )
            self.connection.commit()
        except Exception as e:
            print(f"⚠️ [DB] Миграция partner_id: {e}")

    def _connect(self, silent=True):
        """Внутренний метод подключения к БД"""
        try:
            self._connection = PostgresConnectionAdapter(
                self.host, self.port, self.user, self.password, self.dbname
            )
            self._cursor = self._connection.cursor()
            if not silent:
                print("✅ [DB] Успешное подключение к PostgreSQL")
            return True
        except Exception as e:
            if not silent:
                print(f"❌ [DB] Ошибка подключения к PostgreSQL: {e}")
            self._connection = None
            self._cursor = None
            return False

    @property
    def connection(self):
        """
        Ленивое свойство для получения соединения.
        Если соединения нет, пытается переподключиться.
        """
        if self._connection is None:
            print("⚠️ [DB] Соединение отсутствует, попытка переподключения...")
            if not self._connect(silent=False):
                raise ConnectionError("Не удалось установить соединение с базой данных PostgreSQL")
        return self._connection

    @property
    def cursor(self):
        """
        Ленивое свойство для получения курсора.
        Возвращает "липкий" курсор для текущего потока.
        """
        if not hasattr(self._thread_local, 'cursor') or self._thread_local.cursor is None:
            self._thread_local.cursor = self.connection.cursor()
        return self._thread_local.cursor

    def return_connect(self):
        return self.connection

    # ======================================================================================================================
    # ===== ТАБЛИЦА: users =================================================================================================
    # ======================================================================================================================

    # --- Добавить значение ---

    def add_users_user(self, user_id, user_link, user_reg_time, user_name=None, user_first_name=None,
                       user_last_name=None, coin_count=0):
        """Добавление пользователя в новую БД (Profile)"""
        with self.connection:
            # В новой БД Profile: user_id, Phone, Fio, Age, Sex, Style, Kcal, prefer, Hate, Mood, Hungry, Experiments, Reviews
            # Fio формируем из user_first_name и user_last_name
            fio = f"{user_first_name or ''} {user_last_name or ''}".strip() if (user_first_name or user_last_name) else None
            self.cursor.execute(
                "INSERT INTO Profile (user_id, Fio) VALUES (?, ?)",
                (user_id, fio))
            self.connection.commit()

    def del_users_user(self, user_id):
        with self.connection:
            return self.cursor.execute(
                "DELETE FROM users WHERE user_id = ?",
                (user_id,))

    def check_users_user_exists(self, user_id):
        """Проверка существования пользователя в новой БД (таблица Profile)"""
        with self.connection:
            result = self.cursor.execute("SELECT * FROM Profile WHERE user_id=?", (user_id,)).fetchall()
            return bool(len(result))

        # --- Ban ---

    def set_users_ban(self, user_id: int, ban: int):
        with self.connection:
            self.cursor.execute("UPDATE users SET ban = ? WHERE user_id = ?", (ban, user_id))

    def get_users_ban(self, user_id) -> dict:
        with self.connection:
            result = self.connection.execute("SELECT ban FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()
            return bool(int(result[0][0]))

        # --- Mode ---

    def set_users_mode(self, user_id: int, mode_id: int, mode_key: str):
        with self.connection:
            self.cursor.execute("UPDATE users SET mode_id = ?, mode_key = ? WHERE user_id = ?",
                                (mode_id, mode_key, user_id))

    def get_users_mode(self, user_id) -> dict:
        with self.connection:
            result = self.connection.execute("SELECT mode_id, mode_key FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()
            return {'id': int(result[0][0]), 'key': str(result[0][1])}

        # --- Message ---

    def set_users_first_message(self, user_id, id):
        with self.connection:
            return self.cursor.execute("UPDATE users SET first_message = ? WHERE user_id = ?", (id, user_id))

    def get_users_first_message(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT first_message FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()
            for row in result:
                id = str(row[0])
                return id
            return 0

    def set_users_last_message(self, user_id, id):
        with self.connection:
            return self.cursor.execute("UPDATE users SET last_message = ? WHERE user_id = ?", (id, user_id))

    def get_users_last_message(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT last_message FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()
            for row in result:
                id = str(row[0])
                return id
            return 0

        # --- User link ---

    def get_users_user_link(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT user_link FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()

            for row in result:
                user_link = str(row[0])
            return user_link

        # --- User name ---

    def get_users_user_name(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT user_name FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()

            for row in result:
                user_name = str(row[0])
            return user_name

        # --- User first name ---

    def get_users_user_first_name(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT user_first_name FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()

            for row in result:
                user_first_name = str(row[0])
            return user_first_name

        # --- User last name ---

    def get_users_user_last_name(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT user_last_name FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()

            for row in result:
                user_last_name = str(row[0])
            return user_last_name

        # --- User reg time ---

    def get_users_user_reg_time(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT user_reg_time FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()

            for row in result:
                user_reg_time = str(row[0])
            return user_reg_time

            # --- User last recommendation time ---

        # def set_users_last_recomendation_time(self, user_id, current_time):
        #             with self.connection:
        #                 return self.cursor.execute(
        #                     "UPDATE users SET last_recomendation_time = ? FROM users WHERE user_id = ?",
        #                     (user_id, current_time))

    def get_users_last_recomendation_time(self, user_id):
        with self.connection:
            result = self.connection.execute("SELECT last_recomendation_time FROM users WHERE user_id = ?",
                                             (user_id,)).fetchall()

        for row in result:
            last_recomendation_time = str(row[0])
            return last_recomendation_time

        # --- Food2Mood Coin

    def add_food_to_mood_coin(self, user_id: int, coin_count: int):
        with self.connection:
            self.cursor.execute("UPDATE users SET foodToMoodCoin = foodToMoodCoin + ? WHERE user_id = ?",
                                (coin_count, user_id))

    def clear_food_to_mood_coin(self, user_id: int):
        with self.connection:
            self.cursor.execute("UPDATE users SET foodToMoodCoin = foodToMoodCoin + ? WHERE user_id = ?", (user_id,))

    def get_users_food_to_mood_coin(self, user_id: int):
        with self.connection:
            result = self.connection.execute("SELECT foodToMoodCoin FROM users WHERE user_id = ?", (user_id,))
            for row in result:
                foodToMoodCoin = str(row[0])
            return foodToMoodCoin

        # --- All users ---

    def get_users_users(self):
        with self.connection:
            result = self.connection.execute("SELECT user_id FROM users").fetchall()
            users_id = []
            for row in result:
                users_id.append(int(row[0]))
            return users_id

    def set_users_phone(self, user, phone):
        """Установка телефона пользователя в новой БД (Profile.Phone). Телефон нормализуется автоматически."""
        # Нормализуем телефон перед сохранением
        normalized_phone = normalize_phone(phone)
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Phone = ? WHERE user_id = ?", (normalized_phone, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Phone) VALUES (?, ?)", (user, normalized_phone))
            self.connection.commit()

    def get_users_phone(self, user):
        with self.connection:
            result = self.cursor.execute(
                "SELECT phone FROM users WHERE user_id = ?",
                (user,)).fetchall()
        try:
            return result[0][0]
        except:
            return None

    def set_users_partner_id(self, user_id, partner_id):
        """Установка partner_id пользователя в Profile."""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET partner_id = ? WHERE user_id = ?", (partner_id, user_id))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, partner_id) VALUES (?, ?)", (user_id, partner_id))
            self.connection.commit()

    def get_user_by_partner_id(self, partner_id):
        """Поиск пользователя по partner_id. Возвращает user_id или None."""
        with self.connection:
            result = self.cursor.execute(
                "SELECT user_id FROM Profile WHERE partner_id = ?",
                (partner_id,)).fetchone()
        if result:
            return result[0]
        return None

    # ======================================================================================================================
    # ===== ТАБЛИЦА: menu =================================================================================================
    # ======================================================================================================================
    # --- all categories ---
    # --- all categories ---
    def restaurants_get_dish(self, dish) -> list:
        if type(dish) is list:
            dish = dish[0]
        if '»' in dish:
            dish = dish[1:-1]
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM menu WHERE dish_name = ?",
                (dish,)).fetchall()
            return result[0]

    def get_all_categories(self):
        with self.connection:
            result = self.connection.execute("SELECT Category FROM Menu").fetchall()
            # Использование множества для удаления дубликатов и преобразование его обратно в список
            unique_categories = list(set(category[0] for category in result if category[0]))
            return unique_categories

    def restaurants_find_all(self, keyword):
        with self.connection:
            self.connection.execute("DROP TABLE IF EXISTS rest_fts")
            self.connection.execute("CREATE VIRTUAL TABLE rest_fts USING fts4(id, rest_name, rest_address)")
            self.connection.execute("INSERT INTO rest_fts(id, rest_name, rest_address) "
                                    "SELECT id, rest_name, rest_address "
                                    "FROM menu")
            result = self.connection.execute(
                f"SELECT id, rest_name, rest_address FROM rest_fts WHERE rest_name LIKE '%{keyword}%' OR rest_address LIKE '%{keyword}%'").fetchall()
            all_posts = []
            rest = []
            for row in result:
                row = list(row)
                if [row[1], row[2]] not in rest:
                    all_posts.append(row)
                    rest.append([row[1], row[2]])
            return all_posts

    def restaurants_find_address(self, rest_name):
        with self.connection:
            result = self.connection.execute(
                f"SELECT rest_address FROM menu WHERE rest_name LIKE '%{rest_name}%'").fetchone()
            return result[0]

    def restaurants_find_dish(self, rest_name, keyword):
        with self.connection:
            self.connection.execute("DROP TABLE IF EXISTS dish_fts")
            self.connection.execute(
                "CREATE VIRTUAL TABLE dish_fts USING fts4(id, rest_name, rest_address, dish_name)")
            self.connection.execute("INSERT INTO dish_fts(id, rest_name, rest_address, dish_name) "
                                    "SELECT id, rest_name, rest_address, dish_name "
                                    "FROM menu")
            # self.connection.execute(f"SELECT * FROM dish_fts WHERE dish_name LIKE '%{keyword}%'")
            result = self.connection.execute(
                f"SELECT * FROM dish_fts WHERE rest_name = '{rest_name}' AND dish_name LIKE '%{keyword}%'").fetchall()
            return result

    def restaurants_get_all(self):
        with self.connection:
            result = self.connection.execute(
                "SELECT id, rest_name, rest_address FROM menu").fetchall()
            all_posts = []
            rest = []
            for row in result:
                row = list(row)
                if [row[1], row[2]] not in rest:
                    all_posts.append(row)
                    rest.append([row[1], row[2]])
            return all_posts

    def restaurants_get_all_dish(self):
        with self.connection:
            result = self.connection.execute(
                "SELECT id, dish_name FROM menu").fetchall()
            return result

    def menu_get(self, menu_id: Optional[str] = None) -> list:
        """Получение меню из новой БД (таблица Menu)
        
        Args:
            menu_id: Опциональный фильтр по ID меню. Если указан, возвращаются только блюда с соответствующим menu_id.
        """
        with self.connection:
            # Возвращаем в формате, совместимом со старой структурой
            # Старая: id, Категория, Название, Комментарий, Ингредиенты, Простые ингредиенты, КБЖУ, Граммы, Цена, Размер, iiko_id, Стиль, Настроение, ...
            # Новая: Dish_id, menu_id, Restaurant, Category, Name, Ingredients, Kcal, Price, Weight, Dish_tags, iiko_id, mood
            # Возвращаем: Dish_id, Category, Name, NULL, Ingredients, NULL, Kcal, Weight, Price, Dish_tags, iiko_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL, category_iiko_id, mood, simple_ingredients, ai_comment
            # Индексы: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21
            if menu_id:
                # Получаем блюда конкретного меню
                result = self.connection.execute(
                    "SELECT Dish_id, Category, Name, Restaurant, Ingredients, NULL, Kcal, Weight, Price, Dish_tags, iiko_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL, COALESCE(category_iiko_id, NULL) as category_iiko_id, COALESCE(mood, NULL) as mood, COALESCE(simple_ingredients, NULL) as simple_ingredients, COALESCE(ai_comment, NULL) as ai_comment FROM Menu WHERE menu_id = ?",
                    (menu_id,)
                ).fetchall()
            else:
                # Получаем все меню
                result = self.connection.execute(
                    "SELECT Dish_id, Category, Name, Restaurant, Ingredients, NULL, Kcal, Weight, Price, Dish_tags, iiko_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL, COALESCE(category_iiko_id, NULL) as category_iiko_id, COALESCE(mood, NULL) as mood, COALESCE(simple_ingredients, NULL) as simple_ingredients, COALESCE(ai_comment, NULL) as ai_comment FROM Menu").fetchall()
            return result

    def get_dish_id(self, restaurant, name) -> list:
        with self.connection:
            result = self.connection.execute(
                "SELECT id FROM menu WHERE rest_name = ? and dish_name = ?",
                (restaurant, name)).fetchone()[0]
            return result

    def get_dish_price(self, id) -> str:
        with self.connection:
            result = self.cursor.execute(
                "SELECT dish_price FROM menu WHERE id = ?",
                (id,)).fetchall()
        return result

    def get_g(self, id) -> str:
        with self.connection:
            result = self.connection.execute(
                "SELECT dish_g FROM menu WHERE id = ?",
                (id,)).fetchall()
            return result

    # --- Взять рекомендации ---

    def restaurants_get_dish_rec_nutritionist(self, restaurant: str) -> list:
        with self.connection:
            result = self.connection.execute(
                "SELECT dish_rec_nutritionist FROM menu WHERE rest_name = ?",
                (restaurant,)).fetchall()
            if len(result):
                if len(result[0]):
                    if result[0][0] is None:
                        return []
                    return result

    def restaurants_get_dish_rec_community(self, restaurant: str) -> list:
        with self.connection:
            result = self.connection.execute(
                "SELECT dish_rec_community FROM menu WHERE rest_name = ?",
                (restaurant,)).fetchall()
            if len(result):
                if len(result[0]):
                    if result[0][0] is None:
                        return []
                    return result

    def restaurants_get_dish_rec_a_oblomov(self, restaurant: str) -> list:
        with self.connection:
            result = self.connection.execute(
                "SELECT dish_rec_a_oblomov FROM menu WHERE rest_name = ?",
                (restaurant,)).fetchall()
            if len(result):
                if len(result[0]):
                    if result[0][0] is None:
                        return []
                    return result

    def restaurants_get_dish_rec_a_ivlev(self, restaurant: str) -> list:
        with self.connection:
            result = self.connection.execute(
                "SELECT dish_rec_a_ivlev FROM menu WHERE rest_name = ?",
                (restaurant,)).fetchall()
            if len(result):
                if len(result[0]):
                    if result[0][0] is None:
                        return []
                    return result

    def restaurants_get_by_id(self, id) -> list:
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM menu WHERE id = ?",
                (id,)).fetchall()
            return result[0]

    def restaurants_get_by_name(self, dish_name: str) -> list:
        """Получение блюда по имени из новой БД (таблица Menu)"""
        with self.connection:
            result = self.connection.execute(
                "SELECT Dish_id, Category, Name, NULL, Ingredients, NULL, Kcal, Weight, Price, NULL, iiko_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM Menu WHERE Name = ?",
                (dish_name,)).fetchall()
            if result:
                return result[0]
            return None

    # --- review ---

    def restaurants_set_review(self, id: int, review: str):
        review = review.lower()

        symbols_to_remove = ":;/<>"

        for symbol in symbols_to_remove:
            review = review.replace(symbol, "")

        reviews = self.restaurants_get_review(id) + " ; " + review

        with self.connection:
            self.cursor.execute(
                "UPDATE menu SET stat_reviews = ? WHERE id = ?",
                (reviews, id))

    def restaurants_get_review(self, id: int) -> str:
        with self.connection:
            result = self.connection.execute(
                "SELECT stat_reviews FROM menu WHERE id = ?",
                (id,)).fetchall()
            return str(result[0][0])

    # --- rating ---

    def restaurants_set_rating(self, id: int, rating: int):

        ratings = self.restaurants_get_rating(id) + " ; " + str(rating)

        with self.connection:
            self.cursor.execute(
                "UPDATE menu SET stat_rating = ? WHERE id = ?",
                (ratings, id))

    def restaurants_get_rating(self, id: int) -> str:
        with self.connection:
            result = self.connection.execute(
                "SELECT stat_rating FROM menu WHERE id = ?",
                (id,)).fetchall()
            return str(result[0][0])

    def get_simple_ingredients(self, rest_name, dish_name):
        with self.connection:
            result = self.connection.execute(
                "SELECT simple_ingredients FROM menu WHERE rest_name = ? and dish_name = ?",
                (rest_name, dish_name)
            ).fetchone()
            return result[0] if result else None

    # --- for waiters ---

    def additional_dishes(self, dish_name):
        with self.connection:
            result = self.connection.execute(
                "SELECT additional_dishes FROM menu WHERE dish_name = ?", (dish_name,)
            ).fetchall()
        if result:
            return result[0][0]
        else:
            return None

    def get_dish_modifiers(self, dish_id: int) -> list:
        """Получить модификаторы блюда из колонки modifiers (jsonb) таблицы Menu."""
        try:
            with self.connection:
                result = self.cursor.execute(
                    "SELECT modifiers FROM Menu WHERE Dish_id = ?",
                    (dish_id,)
                ).fetchone()
                if result and result[0]:
                    mods = result[0]
                    if isinstance(mods, str):
                        return json.loads(mods)
                    return mods
                return []
        except Exception as e:
            print(f"❌ [MODIFIERS] Ошибка получения модификаторов для dish_id={dish_id}: {e}")
            return []

    def set_dish_modifiers(self, dish_id: int, modifiers: list):
        """Установить модификаторы блюда."""
        try:
            with self.connection:
                mods_json = json.dumps(modifiers, ensure_ascii=False)
                self.cursor.execute(
                    "UPDATE Menu SET modifiers = ?::jsonb WHERE Dish_id = ?",
                    (mods_json, dish_id)
                )
                self.connection.commit()
        except Exception as e:
            print(f"❌ [MODIFIERS] Ошибка установки модификаторов для dish_id={dish_id}: {e}")

    # ------

    def get_dish_size(self, id):
        with self.connection:
            result = self.connection.execute(
                "SELECT size FROM menu WHERE id = ?", (id,)
            ).fetchall()
        return str(result[0][0])

    # ======================================================================================================================
    # ===== ТАБЛИЦА: waiters =================================================================================================
    # ======================================================================================================================

    # --- Добавить значение ---

    def add_waiter(self, user_id, user_link, user_name=None, user_last_name=None, user_first_name=None,
                   user_surname=None, score="[]", restaurant=None):

        with self.connection:
            return self.cursor.execute(
                "INSERT INTO waiters (waiter_id, waiter_link, waiter_name, waiter_last_name,"
                " waiter_first_name, waiter_surname, waiter_score, waiter_rest) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, user_link, user_name, user_last_name, user_first_name, user_surname, score, restaurant))

    def update_waiter_restaurant(self, waiter_id, restaurant):
        """Обновить ресторан официанта."""
        with self.connection:
            self.cursor.execute(
                "UPDATE waiters SET waiter_rest = ? WHERE waiter_id = ?",
                (restaurant, waiter_id))
            self.connection.commit()

    def get_restaurants_list(self):
        """Получить список ресторанов из таблицы menu (динамически)."""
        try:
            result = self.cursor.execute(
                "SELECT DISTINCT restaurant FROM menu WHERE restaurant IS NOT NULL ORDER BY restaurant"
            ).fetchall()
            return [r[0] for r in result] if result else []
        except Exception as e:
            print(f"❌ Ошибка получения списка ресторанов: {e}")
            return []

    def del_waiter(self, user_id):
        with self.connection:
            return self.cursor.execute(
                "DELETE FROM waiters WHERE waiter_id = ?",
                (user_id,))

    def check_waiter_exists(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM waiters WHERE waiter_id=?", (user_id,)).fetchall()
            return bool(len(result))

    def set_waiter_score(self, user_id: int, score: str):
        with self.connection:
            self.cursor.execute(
                "UPDATE waiters SET waiter_score = ? WHERE waiter_id = ?",
                (score, user_id))

    def get_waiter_score(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT waiter_score FROM waiters WHERE waiter_id=?",
                                         (user_id,)).fetchall()
            return result[0][0]

    def get_waiters_waiters(self):
        with self.connection:
            result = self.connection.execute("SELECT waiter_id FROM waiters").fetchall()
            users_id = []
            for row in result:
                users_id.append(int(row[0]))
            return users_id

    def get_waiters_names_and_stats(self):
        with self.connection:
            result = self.connection.execute(
                "SELECT waiter_id, waiter_last_name, waiter_first_name, waiter_surname, "
                "waiter_score, waiter_current_earnings, waiter_name FROM waiters").fetchall()
            return result

    def get_remark(self, waiter_id):
        with self.connection:
            result = self.connection.execute("SELECT waiter_remark FROM waiters WHERE waiter_id=?",
                                             (waiter_id,)).fetchall()
        return result[0][0]

    def set_remark(self, waiter_id, remark):
        with self.connection:
            self.cursor.execute(
                "UPDATE waiters SET waiter_remark = ? WHERE waiter_id = ?",
                (remark, waiter_id))

    def clear_remark(self, waiter_id):
        with self.connection:
            self.cursor.execute(
                "UPDATE waiters SET waiter_remark = ? WHERE waiter_id = ?",
                ('', waiter_id))

    def get_current_earnings(self, waiter_id):
        with self.connection:
            result = self.cursor.execute(
                "SELECT waiter_current_earnings FROM waiters WHERE waiter_id = ?",
                (waiter_id,)).fetchone()
            return float(result[0]) if result and result[0] is not None else 0

    def set_current_earnings(self, amount, waiter_id):
        with self.connection:
            self.cursor.execute(
                "UPDATE waiters SET waiter_current_earnings = ? WHERE waiter_id = ?",
                (amount, waiter_id))

    def return_waiter_rest(self, waiter):
        with self.connection:
            result = self.cursor.execute(
                "SELECT waiter_rest FROM waiters WHERE waiter_id = ?",
                (waiter,)).fetchall()
        return result[0][0].split(':')[0]

    # ======================================================================================================================
    # ===== ТАБЛИЦА: baskets =================================================================================================
    # ======================================================================================================================

    def create_basket(self, user_id, basket="{}"):
        """Создание корзины в новой БД (Orders)"""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO Orders (user_id, basket) VALUES (?, ?)",
                (user_id, json.dumps(basket)))
            self.connection.commit()

    def check_basket_exists(self, user_id):
        """Проверка существования корзины в новой БД (таблица Orders)"""
        with self.connection:
            result = self.cursor.execute("SELECT * FROM Orders WHERE user_id=?", (user_id,)).fetchall()
            return bool(len(result))

    def set_basket(self, user_id, basket):
        """Установка корзины в новой БД (Orders.basket)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Orders WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute(
                    "UPDATE Orders SET basket = ? WHERE user_id = ?",
                    (json.dumps(basket), user_id))
            else:
                self.cursor.execute(
                    "INSERT INTO Orders (user_id, basket) VALUES (?, ?)",
                    (user_id, json.dumps(basket)))
            self.connection.commit()

    def get_basket(self, user_id):
        """Получение корзины из новой БД (Orders.basket)"""
        with self.connection:
            result = self.cursor.execute("SELECT basket FROM Orders WHERE user_id=?", (user_id,)).fetchone()
            if result and result[0]:
                try:
                    return json.loads(result[0])
                except (json.JSONDecodeError, TypeError):
                    return {}
            return {}

    def set_qr_scanned(self, user_id, qr_scanned):
        """Установка флага сканирования QR в новой БД (в Orders нет этого поля, пропускаем)"""
        # В новой БД нет поля qr_scanned, поэтому просто пропускаем
        pass

    def get_qr_scanned(self, user_id):
        """Получение флага сканирования QR (в новой БД нет этого поля, возвращаем False)"""
        return False

    def set_qr_id(self, user_id, qr_id):
        """Установка QR ID (в новой БД нет этого поля, пропускаем)"""
        # В новой БД нет поля qr_id, поэтому просто пропускаем
        pass

    def get_qr_id(self, user_id):
        """Получение QR ID (в новой БД нет этого поля, возвращаем None)"""
        return None

    def del_basket(self, user_id):
        with self.connection:
            return self.cursor.execute(
                "DELETE FROM baskets WHERE user_id = ?",
                (user_id,))

    # ======================================================================================================================
    # ===== ТАБЛИЦА: user_actions =================================================================================================
    # ======================================================================================================================

    def get_last_session(self, user_id):
        self.cursor.execute('''
            SELECT session_num, actions, start_time, end_time
            FROM user_actions
            WHERE user_id = ?
            ORDER BY start_time DESC
            LIMIT 1
        ''', (user_id,))
        result = self.cursor.fetchone()
        return result

    def create_new_session(self, user_id, action):
        try:
            last_session = self.get_last_session(user_id)
        except:
            last_session = False
        SESSION_TIMEOUT = datetime.timedelta(hours=3)
        if last_session:
            last_session_num = last_session[0]
            last_start_time = datetime.datetime.strptime(last_session[2], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() - last_start_time > SESSION_TIMEOUT:
                new_session_num = last_session_num + 1
            else:
                new_session_num = last_session_num
        else:
            new_session_num = 1
        current_time = datetime.datetime.now().replace(microsecond=0)

        self.cursor.execute('''
            INSERT INTO user_actions (user_id, session_num, actions, start_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, new_session_num, action, current_time.strftime('%Y-%m-%d %H:%M:%S')))

    def update_session(self, user_id, action):
        try:
            last_session = self.get_last_session(user_id)
        except:
            last_session = False
        if last_session:
            session_num, actions, start_time, end_time = last_session
            updated_actions = actions + '->' + action
            self.cursor.execute('''
                UPDATE user_actions
                SET actions = ?, end_time = ?
                WHERE user_id = ? AND session_num = ?
            ''', (updated_actions, datetime.datetime.now().replace(microsecond=0), user_id, session_num))

    def add_user_action(self, user_id, action):
        SESSION_TIMEOUT = datetime.timedelta(hours=3)
        try:
            last_session = self.get_last_session(user_id)
        except:
            last_session = False
        if last_session:
            last_start_time = datetime.datetime.strptime(last_session[2], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() - last_start_time > SESSION_TIMEOUT:
                self.create_new_session(user_id, action)
            else:
                self.update_session(user_id, action)
        else:
            self.create_new_session(user_id, action)

    def check_last_action(self, user_id, action):
        try:
            last_session = self.get_last_session(user_id)
        except:
            return False
        if not last_session:
            return False
        last_action = last_session[1].split('->')
        if last_action[-1] == action:
            return True

    # ======================================================================================================================
    # ===== ТАБЛИЦА: stop_lists =================================================================================================
    # ======================================================================================================================

    def create_stop_list(self, rest, stop_list="{}"):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO stop_lists (rest, stop_list) VALUES (?, ?)",
                (rest, stop_list))

    def check_stop_list_exists(self):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM stop_lists").fetchall()
            return bool(len(result))

    def set_stop_list(self, stop_list):
        with self.connection:
            self.cursor.execute(
                "UPDATE stop_lists SET stop_list = ?",
                (stop_list,))

    def get_stop_list(self, rest):
        with self.connection:
            result = self.cursor.execute("SELECT stop_list FROM stop_lists WHERE rest=?", (rest,)).fetchall()
            return result[0][0]

    def del_stop_list(self, rest):
        with self.connection:
            return self.cursor.execute(
                "DELETE FROM stop_lists WHERE rest = ?",
                (rest,))

    def get_stop_list_dish_ids(self, rest: str) -> list:
        """Получить список Dish_id блюд из стоп-листа ресторана."""
        try:
            raw = self.get_stop_list(rest)
            if not raw:
                return []
            stop_data = json.loads(raw) if isinstance(raw, str) else raw
            # stop_data может быть dict {dish_name: ...} или list
            if isinstance(stop_data, dict):
                stopped_names = list(stop_data.keys())
            elif isinstance(stop_data, list):
                stopped_names = stop_data
            else:
                return []

            if not stopped_names:
                return []

            # Находим Dish_id по именам
            all_menu = self.menu_get()
            dish_ids = []
            stopped_lower = {n.strip().lower() for n in stopped_names}
            for dish in all_menu:
                if dish[2] and dish[2].strip().lower() in stopped_lower:
                    dish_ids.append(dish[0])
            return dish_ids
        except Exception as e:
            print(f"❌ [STOP-LIST] Ошибка получения dish_ids: {e}")
            return []

    # ======================================================================================================================
    # ===== ТАБЛИЦА: total_and_current_counts =================================================================================================
    # ======================================================================================================================

    def add_rest(self, rest, total_click_count=0, current_click_count=0, last_check_time=""):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO total_and_current_counts (rest, total_click_count, current_click_count,"
                " last_check_time) VALUES (?, ?, ?, ?)",
                (rest, total_click_count, current_click_count, last_check_time))

    def check_rest_exists(self, rest):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM total_and_current_counts WHERE rest=?", (rest,)).fetchall()
            return bool(len(result))

    def set_total_click_count(self, total_click_count):
        with self.connection:
            self.cursor.execute(
                "UPDATE total_and_current_counts SET total_click_count = ?",
                (total_click_count,))

    def get_total_click_count(self):
        with self.connection:
            result = self.cursor.execute("SELECT total_click_count FROM total_and_current_counts").fetchall()
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def set_current_click_count(self, current_click_count):
        with self.connection:
            self.cursor.execute(
                "UPDATE total_and_current_counts SET current_click_count = ?",
                (current_click_count,))

    def get_current_click_count(self):
        with self.connection:
            result = self.cursor.execute("SELECT current_click_count FROM total_and_current_counts").fetchall()
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def set_last_check_time(self, time):
        with self.connection:
            self.cursor.execute(
                "UPDATE total_and_current_counts SET last_check_time = ?",
                (time,))

    def get_last_check_time(self):
        with self.connection:
            result = self.cursor.execute("SELECT last_check_time FROM total_and_current_counts").fetchall()
            if len(result) > 0:
                return result[0][0]
            else:
                return None

    def del_rest(self, rest):
        with self.connection:
            return self.cursor.execute(
                "DELETE FROM total_and_current_counts WHERE rest = ?",
                (rest,))

    # ======================================================================================================================
    # ===== ТАБЛИЦА: admins =================================================================================================
    # ======================================================================================================================

    # --- Добавить значение ---

    def add_admin(self, user_id, user_rest):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO admins (admin_id, temp_rest) VALUES (?, ?)",
                (user_id, user_rest))

    def del_admin(self, user_id):
        with self.connection:
            return self.cursor.execute(
                "DELETE FROM admins WHERE admin_id = ?",
                (user_id,))

    def check_admin_exists(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM admins WHERE admin_id=?", (user_id,)).fetchall()
            return bool(len(result))

    def set_admin_rest(self, user_id, rest):
        with self.connection:
            self.cursor.execute("UPDATE admins SET temp_rest = ? WHERE admin_id = ?", (rest, user_id,)).fetchall()

    def get_admin_rest(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT temp_rest FROM admins WHERE admin_id=?", (user_id,)).fetchall()
            return result[0][0]

    # ======================================================================================================================
    # ===== ТАБЛИЦА: orders =================================================================================================
    # ======================================================================================================================

    # --- Добавить значение ---

    def add_order(self, user_id, table_number, time, amount, restaurant_name=None, waiter_id=None):
        """Добавление заказа в новую БД (Orders)"""
        with self.connection:
            # В новой БД Orders: user_id, basket, `table number`, total_price, restaurant_name
            # Обновляем существующую запись или создаем новую
            exists = self.cursor.execute("SELECT user_id FROM Orders WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute(
                    'UPDATE Orders SET "table number" = ?, total_price = ? WHERE user_id = ?',
                    (str(table_number), str(amount), user_id))
            else:
                self.cursor.execute(
                    'INSERT INTO Orders (user_id, "table number", total_price) VALUES (?, ?, ?)',
                    (user_id, str(table_number), str(amount)))
            self.connection.commit()
            
            # Получаем корзину для истории
            basket_json = "{}"
            try:
                # Используем отдельный курсор или запрос, чтобы не сбить транзакцию? 
                # В sqlite/postgres внутри with self.connection можно делать несколько запросов
                b_res = self.cursor.execute("SELECT basket FROM Orders WHERE user_id=?", (user_id,)).fetchone()
                if b_res and b_res[0]:
                    basket_json = b_res[0]
            except Exception as e:
                print(f"Error getting basket for history: {e}")

            # Сохраняем в историю заказов
            self.save_order_history(
                user_id=user_id,
                basket=basket_json,
                table_number=str(table_number),
                total_price=str(amount),
                order_status='created',
                restaurant_name=restaurant_name,
                waiter_id=waiter_id
            )

    def add_waiter_order(self, waiter_id, table_number, time, amount, rest=None):
        """Добавление заказа официанта в таблицу orders (заказы официантов)"""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO orders (waiter_id, rest, table_number, time, order_amount) VALUES (?, ?, ?, ?, ?)",
                (waiter_id, rest or "", table_number, time, amount))
            self.connection.commit()

    def get_current_guests_count(self):
        current_time = datetime.datetime.now().strftime("%Y-%m-%d")
        with self.connection:
            result = self.cursor.execute(f"SELECT time FROM orders WHERE time LIKE '%{current_time}%'").fetchall()
            if result:
                return len(result)
            else:
                return 0

    def get_current_waiter_guests(self, waiter_id):
        current_time = datetime.datetime.now().strftime("%Y-%m-%d")
        with self.connection:
            result = self.cursor.execute(
                f"SELECT time FROM orders WHERE waiter_id=? AND time LIKE '%{current_time}%'",
                (waiter_id,)).fetchall()
            if result:
                return len(result)
            else:
                return 0

    def get_current_waiter_sells(self, waiter_id):
        current_time = datetime.datetime.now().strftime("%Y-%m-%d")
        with self.connection:
            result = self.cursor.execute(
                f"SELECT order_amount FROM orders WHERE waiter_id=? AND time LIKE '%{current_time}%'",
                (waiter_id,)).fetchall()
            if result:
                return sum([int(e[0]) for e in result])
            else:
                return 0

    # ======================================================================================================================
    # ===== ТАБЛИЦА: orders_history =================================================================================================
    # ======================================================================================================================

    def add_users_order(self, user_id, rest, basket):
        with self.connection:
            return self.cursor.execute("INSERT INTO orders_history (user_id, rest, basket) VALUES (?, ?, ?)",
                                       (user_id, rest, basket))

    def get_last_users_order(self, user_id):
        with self.connection:
            result = self.cursor.execute(f"SELECT rest FROM orders_history WHERE user_id={user_id}").fetchall()
            return result[-1]

    # ======================================================================================================================
    # ===== ТАБЛИЦА: client_rest_search =================================================================================================
    # ======================================================================================================================

    def add_search_filters(self, user_id, filters):
        with self.connection:
            return self.cursor.execute("INSERT INTO client_rest_search (id, filters, temp_rest) VALUES (?, ?, ?)",
                                       (user_id, filters, 0))

    def check_filters_exists(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM client_rest_search WHERE id=?", (user_id,)).fetchall()
            return bool(len(result))

    def set_search_filters(self, user_id, filters):
        with self.connection:
            self.cursor.execute("UPDATE client_rest_search SET filters=? WHERE id=?",
                                (filters, user_id,)).fetchall()

    def get_search_filters(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT filters FROM client_rest_search WHERE id=?", (user_id,)).fetchall()
            return result[0][0]

    def set_temp_rest(self, user_id, temp_rest):
        with self.connection:
            self.cursor.execute("UPDATE client_rest_search SET temp_rest=? WHERE id=?",
                                (temp_rest, user_id,)).fetchall()

    def get_temp_rest(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT temp_rest FROM client_rest_search WHERE id=?",
                                         (user_id,)).fetchall()
            return result[0][0]

    # ======================================================================================================================
    # ===== ТАБЛИЦА: F2M_reviews =================================================================================================
    # ======================================================================================================================
    def add_reason(self, user_id, reason, star):
        with self.connection:
            return self.cursor.execute('INSERT INTO F2M_reviews (user_id, review, star) VALUES (?, ?, ?)',
                                       (user_id, reason, star))

    # ======================================================================================================================
    # ===== ТАБЛИЦА: iiko_data =================================================================================================
    # ======================================================================================================================

    def check_token(self, rest, api):
        try:
            with self.connection:
                result = self.cursor.execute("SELECT token_time_start FROM iiko_data WHERE rest_name = ?",
                                             (rest,)).fetchone()
                BASE_URL = "https://api-ru.iiko.services/api/1/"
                api_key = api

                if result:
                    date_format = "%Y-%m-%d %H:%M:%S.%f"
                    date_object = datetime.datetime.strptime(result[0], date_format)
                    one_hour = datetime.timedelta(hours=1)
                    time_diff = datetime.datetime.now() - date_object

                    if time_diff > one_hour:
                        self.cursor.execute("DELETE FROM iiko_data WHERE rest_name = ?", (rest,))
                        self.connection.commit()
                        return self.check_token(rest, api)

                    token = self.cursor.execute("SELECT iiko_rest_token FROM iiko_data WHERE rest_name = ?",
                                                (rest,)).fetchone()[0]
                    return token
                else:
                    url = f"{BASE_URL}access_token"
                    params = {"apiLogin": api_key}
                    response = requests.post(url, json=params)

                    if response.status_code != 200:
                        raise Exception(f"Failed to get token: {response.status_code}")

                    token = response.json().get("token")
                    if not token:
                        raise Exception("No token in response")

                    self.cursor.execute(
                        "INSERT INTO iiko_data (rest_name, iiko_rest_token, token_time_start) VALUES (?, ?, ?)",
                        (rest, token, datetime.datetime.now())
                    )
                    self.connection.commit()
                    return token

        except Exception as e:
            raise

    # ======================================================================================================================
    # ===== Действия с iiko_f =================================================================================================
    # ======================================================================================================================
    def get_iiko_id_by_name(self, name):
        """Получение iiko_id по имени блюда из новой БД (Menu.iiko_id)"""
        with self.connection:
            result = self.connection.execute(
                'SELECT iiko_id FROM Menu WHERE Name = ?',
                (name,)).fetchone()
        if result and result[0]:
            return result[0]
        return None

    def get_name_by_iiko_id(self, iiko_id, rest):
        with self.connection:
            result = self.connection.execute(
                'SELECT dish_name FROM menu WHERE iiko_id = ? and rest_name = ?',
                (iiko_id, rest)).fetchone()
            return result[0]

    # ======================================================================================================================
    # ===== f2m_waiter_bot =================================================================================================
    # ======================================================================================================================

    def get_chat_id_list(self):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM f2m_waiter_bot").fetchall()
            return result

    # ======================================================================================================================
    # ===== correlation_coefficients =================================================================================================
    # ======================================================================================================================

    def if_user_in_cc_table(self, user):
        with self.connection:
            result = self.cursor.execute("SELECT * from correlation_coefficient WHERE user_id = ?", (user,))
        if result[0] is None:
            self.create_cc_dict(user)
        else:
            return True

    def did_user_rate_the_dish(self, user, dish_id):
        with self.connection:
            result = self.cursor.execute(
                "SELECT users_dish_coefficients from correlation_coefficient WHERE user_id = ?", (user,))

    def save_dish_rating(self, user_id: int, dish_id: int, rating: int):
        with self.connection:
            result = self.cursor.execute(
                "SELECT users_dish_coefficients FROM correlation_coefficient WHERE user_id = ?",
                (user_id,)).fetchone()

            if result:
                current_coefficients = eval(result[0]) if result[0] else {}

                if str(dish_id) in current_coefficients:
                    current_data = current_coefficients[str(dish_id)]
                    if isinstance(current_data, dict):
                        current_rating = current_data['rating']
                        current_count = current_data['count']
                        new_rating = ((current_rating * current_count) + rating) / (current_count + 1)
                        current_coefficients[str(dish_id)] = {
                            'rating': new_rating,
                            'count': current_count + 1
                        }
                    else:
                        current_coefficients[str(dish_id)] = {
                            'rating': (current_data + rating) / 2,
                            'count': 2
                        }
                else:
                    current_coefficients[str(dish_id)] = {
                        'rating': rating,
                        'count': 1
                    }

                self.cursor.execute(
                    "UPDATE correlation_coefficient SET users_dish_coefficients = ? WHERE user_id = ?",
                    (str(current_coefficients), user_id)
                )
            else:
                coefficients = {
                    str(dish_id): {
                        'rating': rating,
                        'count': 1
                    }
                }
                self.cursor.execute(
                    "INSERT INTO correlation_coefficient (user_id, users_dish_coefficients) VALUES (?, ?)",
                    (user_id, str(coefficients))
                )

    def create_cc_dict(self, user, cc="{}"):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO correlation_coefficient (rest, users_dish_coefficients) VALUES (?, ?)",
                (user, cc))

    # ======================================================================================================================
    # ===== users_anketa1 =================================================================================================
    # ======================================================================================================================
    def get_users_first_q(self, user_id):
        self.cursor.execute('''
                        SELECT * FROM users_anketa1 
                        WHERE user_id = ?
                    ''', (user_id,))
        row = self.cursor.fetchone()
        return row

    def set_default_q1(self, user_id):
        """Установка дефолтных значений первой анкеты в новой БД (Profile)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Mood = ?, Hungry = ?, Experiments = ? WHERE user_id = ?",
                                  ('Спокойствие', '5/10', 'Мне как обычно', user_id))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Mood, Hungry, Experiments) VALUES (?, ?, ?, ?)",
                                  (user_id, 'Спокойствие', '5/10', 'Мне как обычно'))
            self.connection.commit()

    def set_temp_users_mood(self, user, mood):
        """Установка настроения пользователя в новой БД (Profile.Mood)"""
        with self.connection:
            # Проверяем, существует ли запись
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Mood = ? WHERE user_id = ?", (mood, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Mood) VALUES (?, ?)", (user, mood))
            self.connection.commit()

    def get_temp_users_mood(self, user_id):
        """Получение настроения пользователя из новой БД (Profile.Mood)"""
        with self.connection:
            result = self.cursor.execute("SELECT Mood FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def set_temp_users_hungry(self, user, hungry):
        """Установка уровня голода пользователя в новой БД (Profile.Hungry)"""
        hungry_str = f"{hungry}/10" if isinstance(hungry, (int, float)) else str(hungry)
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Hungry = ? WHERE user_id = ?", (hungry_str, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Hungry) VALUES (?, ?)", (user, hungry_str))
            self.connection.commit()

    def get_temp_users_hungry(self, user_id):
        """Получение уровня голода пользователя из новой БД (Profile.Hungry)"""
        with self.connection:
            result = self.cursor.execute("SELECT Hungry FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                hungry_str = str(result[0])
                # Парсим формат "5/10" или просто число
                if '/' in hungry_str:
                    hungry_value = hungry_str.split('/')[0].strip()
                    try:
                        return int(hungry_value)
                    except ValueError:
                        return None
                else:
                    try:
                        return int(hungry_str)
                    except ValueError:
                        return None
            return None

    def set_temp_users_prefers(self, user, prefer):
        """Установка предпочтений пользователя в новой БД (Profile.Experiments)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Experiments = ? WHERE user_id = ?", (prefer, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Experiments) VALUES (?, ?)", (user, prefer))
            self.connection.commit()

    # ======================================================================================================================
    # ===== users_anketa2 =================================================================================================
    # ======================================================================================================================
    def set_default_q2(self, user_id):
        """Установка дефолтных значений второй анкеты в новой БД (Profile)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Sex = ?, Age = ?, Style = ?, Kcal = ?, prefer = ?, Hate = ? WHERE user_id = ?",
                                  ('пусто', 'пусто', 'Стандартное', 'пусто', 'пусто', 'пусто', user_id))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Sex, Age, Style, Kcal, prefer, Hate) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (user_id, 'пусто', 'пусто', 'Стандартное', 'пусто', 'пусто', 'пусто'))
            self.connection.commit()

    def get_users_second_q(self, user_id):
        self.cursor.execute('''
                        SELECT * FROM users_anketa2
                        WHERE user_id = ?
                    ''', (user_id,))
        row = self.cursor.fetchone()
        return row

    def get_temp_users_ccal(self, user_id):
        """Получение калорийности из новой БД (Profile.Kcal)"""
        with self.connection:
            result = self.cursor.execute("SELECT Kcal FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def set_temp_users_sex(self, user, sex):
        """Установка пола пользователя в новой БД (Profile.Sex)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Sex = ? WHERE user_id = ?", (sex, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Sex) VALUES (?, ?)", (user, sex))
            self.connection.commit()

    def set_temp_users_age(self, user, age):
        """Установка возраста пользователя в новой БД (Profile.Age)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Age = ? WHERE user_id = ?", (age, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Age) VALUES (?, ?)", (user, age))
            self.connection.commit()

    def set_temp_users_food_style(self, user, food_style):
        """Установка стиля питания пользователя в новой БД (Profile.Style)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Style = ? WHERE user_id = ?", (food_style, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Style) VALUES (?, ?)", (user, food_style))
            self.connection.commit()

    def get_temp_users_style(self, user_id):
        """Получение стиля питания из новой БД (Profile.Style)"""
        with self.connection:
            result = self.cursor.execute("SELECT Style FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def set_temp_users_menu_id(self, user, menu_id):
        """Установка menu_id пользователя в новой БД (Profile.menu_id)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET menu_id = ? WHERE user_id = ?", (menu_id, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, menu_id) VALUES (?, ?)", (user, menu_id))
            self.connection.commit()

    def get_temp_users_menu_id(self, user_id):
        """Получение menu_id из новой БД (Profile.menu_id)"""
        with self.connection:
            result = self.cursor.execute("SELECT menu_id FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def set_temp_users_ccal(self, user, ccal):
        """Установка калорийности в новой БД (Profile.Kcal)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Kcal = ? WHERE user_id = ?", (ccal, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Kcal) VALUES (?, ?)", (user, ccal))
            self.connection.commit()

    def set_temp_users_dont_like_to_eat(self, user, dont_like_to_eat):
        """Установка нежелательных продуктов в новой БД (Profile.Hate)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET Hate = ? WHERE user_id = ?", (dont_like_to_eat, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, Hate) VALUES (?, ?)", (user, dont_like_to_eat))
            self.connection.commit()

    def set_temp_users_like_to_eat(self, user, like_to_eat):
        """Установка желаемых продуктов в новой БД (Profile.prefer)"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id=?", (user,)).fetchone()
            if exists:
                self.cursor.execute("UPDATE Profile SET prefer = ? WHERE user_id = ?", (like_to_eat, user))
            else:
                self.cursor.execute("INSERT INTO Profile (user_id, prefer) VALUES (?, ?)", (user, like_to_eat))
            self.connection.commit()

    def get_temp_users_like_to_eat(self, user_id):
        """Получение желаемых продуктов из новой БД (Profile.prefer)"""
        with self.connection:
            result = self.cursor.execute("SELECT prefer FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def get_temp_users_dont_like_to_eat(self, user_id):
        """Получение нежелательных продуктов из новой БД (Profile.Hate)"""
        with self.connection:
            result = self.cursor.execute("SELECT Hate FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if result and result[0]:
                return result[0]
            return None

    # ======================================================================================================================
    # ===== ИИ Profile методы ============================================================================================
    # ======================================================================================================================

    def save_user_profile_json(self, user_id: int, profile_json: str):
        """Сохраняет структурированный ИИ профиль пользователя"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute(
                    "UPDATE Profile SET user_profile_json = ?, profile_updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (profile_json, user_id)
                )
            else:
                self.cursor.execute(
                    "INSERT INTO Profile (user_id, user_profile_json, profile_updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (user_id, profile_json)
                )
            self.connection.commit()
            
            # Сохраняем в историю профилей
            self.save_profile_history(user_id, change_source='api')

    def get_user_profile_json(self, user_id: int) -> Optional[str]:
        """Получает структурированный ИИ профиль пользователя"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT user_profile_json FROM Profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def save_user_temp_sort(self, user_id: int, ranked_menu_json: str):
        """Сохраняет ранжированное меню пользователя в формате MenuResponse"""
        with self.connection:
            exists = self.cursor.execute("SELECT user_id FROM Profile WHERE user_id = ?", (user_id,)).fetchone()
            if exists:
                self.cursor.execute(
                    "UPDATE Profile SET user_temp_sort = ? WHERE user_id = ?",
                    (ranked_menu_json, user_id)
                )
            else:
                self.cursor.execute(
                    "INSERT INTO Profile (user_id, user_temp_sort) VALUES (?, ?)",
                    (user_id, ranked_menu_json)
                )
            self.connection.commit()

    def get_user_temp_sort(self, user_id: int) -> Optional[str]:
        """Получает ранжированное меню пользователя"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT user_temp_sort FROM Profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def get_profile_updated_at(self, user_id: int) -> Optional[str]:
        """Получает дату последнего обновления профиля"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT profile_updated_at FROM Profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None

    # ======================================================================================================================
    # ===== Menu Tags методы ==============================================================================================
    # ======================================================================================================================

    def save_dish_tags_json(self, dish_id: int, tags_json: str):
        """Сохраняет JSON с тегами блюда"""
        with self.connection:
            exists = self.cursor.execute("SELECT Dish_id FROM Menu WHERE Dish_id = ?", (dish_id,)).fetchone()
            if exists:
                self.cursor.execute(
                    "UPDATE Menu SET dish_tags_json = ? WHERE Dish_id = ?",
                    (tags_json, dish_id)
                )
            self.connection.commit()

    def get_menu_id_from_dish(self, dish_id: int) -> Optional[str]:
        """Получает menu_id из блюда по dish_id"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT menu_id FROM Menu WHERE Dish_id = ?",
                (dish_id,)
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def get_dish_tags_json(self, dish_id: int) -> Optional[str]:
        """Получает JSON с тегами блюда"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT dish_tags_json FROM Menu WHERE Dish_id = ?",
                (dish_id,)
            ).fetchone()
            if result and result[0]:
                return result[0]
            return None

    def update_dish_tags(self, dish_id: int, mood: Optional[str] = None, cuisine: Optional[str] = None,
                        style: Optional[str] = None, occasion: Optional[str] = None):
        """Обновляет отдельные поля тегов блюда"""
        with self.connection:
            updates = []
            params = []
            if mood is not None:
                updates.append("dish_mood = ?")
                params.append(mood)
            if cuisine is not None:
                updates.append("dish_cuisine = ?")
                params.append(cuisine)
            if style is not None:
                updates.append("dish_style = ?")
                params.append(style)
            if occasion is not None:
                updates.append("dish_occasion = ?")
                params.append(occasion)
            
            if updates:
                params.append(dish_id)
                query = f"UPDATE Menu SET {', '.join(updates)} WHERE Dish_id = ?"
                self.cursor.execute(query, params)
                self.connection.commit()

    def get_menu_with_tags(self) -> list:
        """Получает все блюда из Menu с тегами"""
        with self.connection:
            result = self.cursor.execute(
                """SELECT Dish_id, Name, Ingredients, Kcal, dish_mood, dish_cuisine, dish_style, 
                   dish_occasion, dish_tags_json FROM Menu"""
            ).fetchall()
            return result

    # ======================================================================================================================
    # ===== users_temp_all =================================================================================================
    # ======================================================================================================================

    def get_users_temp_message_id(self, user_id):
        self.cursor.execute('''SELECT temp_message_id FROM users_temp_all WHERE user_id = ?''', (user_id,))
        row = self.cursor.fetchone()
        return row

    def set_first_temp_mes_id(self, user, m_id):
        self.cursor.execute('''INSERT INTO users_temp_all VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ''',
                            (user, m_id, None, None, None, None, None, None, None))
        self.connection.commit()

    def set_temp_users_message_id(self, user, m_id):
        self.cursor.execute('''UPDATE users_temp_all SET temp_message_id = ? WHERE user_id = ? ''', (m_id, user))
        self.connection.commit()

    def set_temp_users_state(self, user, state):
        self.cursor.execute('''UPDATE users_temp_all SET temp_users_state = ? WHERE user_id = ? ''', (state, user))
        self.connection.commit()

    def get_temp_users_state(self, user):
        self.cursor.execute('''SELECT temp_users_state FROM users_temp_all WHERE user_id = ?''', (user,))
        row = self.cursor.fetchone()
        return row[0]

    def set_first_message_to_delete(self, user, mes):
        self.cursor.execute('''UPDATE users_temp_all SET first_message_to_delete = ? WHERE user_id = ? ''', (mes, user))
        self.connection.commit()

    def get_first_message_to_delete(self, user):
        self.cursor.execute('''SELECT first_message_to_delete FROM users_temp_all WHERE user_id = ?''', (user,))
        row = self.cursor.fetchone()
        return row[0]

    def set_temp_users_category(self, user, category):
        self.cursor.execute('''UPDATE users_temp_all SET temp_users_category = ? WHERE user_id = ? ''',
                            (category, user))
        self.connection.commit()

    def get_temp_users_category(self, user):
        self.cursor.execute('''SELECT temp_users_category FROM users_temp_all WHERE user_id = ?''', (user,))
        row = self.cursor.fetchone()
        return row[0]

    def set_client_temp_dish(self, user_id: int, temp_dish: int):
        temp_dish = max(temp_dish, 0)
        with self.connection:
            self.cursor.execute(
                "UPDATE users_temp_all SET temp_users_dish = ? WHERE user_id = ?",
                (temp_dish, user_id))

    def get_client_temp_dish(self, user_id) -> int:
        with self.connection:
            result = self.connection.execute(
                "SELECT temp_users_dish FROM users_temp_all WHERE user_id = ?",
                (user_id,)).fetchall()
            return int(result[0][0])

    def set_temp_rec(self, user, rec):
        with self.connection:
            self.cursor.execute(
                "UPDATE users_temp_all SET temp_users_rec = ? WHERE user_id = ?",
                (rec, user))

    def get_temp_rec(self, user_id) -> int:
        with self.connection:
            result = self.connection.execute(
                "SELECT temp_users_rec FROM users_temp_all WHERE user_id = ?",
                (user_id,)).fetchall()
            return result[0][0]

    def set_temp_users_dish_id(self, user, rec):
        with self.connection:
            self.cursor.execute(
                "UPDATE users_temp_all SET temp_dish_id = ? WHERE user_id = ?",
                (rec, user))

    def get_temp_users_dish_id(self, user_id) -> int:
        with self.connection:
            result = self.connection.execute(
                "SELECT temp_dish_id FROM users_temp_all WHERE user_id = ?",
                (user_id,)).fetchall()
            return int(result[0][0])

    def set_temp_users_filial(self, user, filial):
        with self.connection:
            self.cursor.execute(
                "UPDATE users_temp_all SET filial = ? WHERE user_id = ?",
                (filial, user))

    def get_temp_users_filial(self, user_id) -> int:
        with self.connection:
            result = self.connection.execute(
                "SELECT filial FROM users_temp_all WHERE user_id = ?",
                (user_id,)).fetchall()
            return (result[0][0])

    # ======================================================================================================================
    # ===== ТАБЛИЦА: prefer_categories =================================================================================================
    # ======================================================================================================================

    def get_prefer_categories(self) -> list:
        """Получить список предпочтительных категорий"""
        with self.connection:
            result = self.connection.execute(
                "SELECT category_name, priority FROM prefer_categories ORDER BY priority ASC"
            ).fetchall()
            return [row[0] for row in result]

    def add_prefer_category(self, category_name: str, priority: int = 0):
        """Добавить категорию в предпочтительные"""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO prefer_categories (category_name, priority) VALUES (?, ?)",
                (category_name, priority)
            )

    def remove_prefer_category(self, category_name: str):
        """Удалить категорию из предпочтительных"""
        with self.connection:
            self.cursor.execute(
                "DELETE FROM prefer_categories WHERE category_name = ?",
                (category_name,)
            )

    def update_prefer_category_priority(self, category_name: str, priority: int):
        """Обновить приоритет категории"""
        with self.connection:
            self.cursor.execute(
                "UPDATE prefer_categories SET priority = ? WHERE category_name = ?",
                (priority, category_name)
            )

    def clear_prefer_categories(self):
        """Очистить все предпочтительные категории"""
        with self.connection:
            self.cursor.execute("DELETE FROM prefer_categories")

    def get_prefer_categories_count(self) -> int:
        """Получить количество предпочтительных категорий"""
        with self.connection:
            result = self.connection.execute("SELECT COUNT(*) FROM prefer_categories").fetchone()
            return result[0]

    # ======================================================================================================================
    # ===== ТАБЛИЦА: logging =================================================================================================
    # ======================================================================================================================

    def add_logging_entry(self, user_id: str, date: str, fio: str = None, phone: str = None,
                          mood: str = None, hungry: str = None, style: str = None, sex: str = None,
                          age: str = None, dish_style: str = None, ccal: str = None,
                          dislike: str = None, like: str = None, order_time: str = None, sum_amount: int = None):
        """Добавить запись в таблицу logging"""
        with self.connection:
            self.cursor.execute("""
                        INSERT INTO logging (user_id, date, fio, phone, mood, hungry, style, sex, age,
                                           dish_style, ccal, dislike, like, "order", sum)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, date, fio, phone, mood, hungry, style, sex, age,
                          dish_style, ccal, dislike, like, order_time, sum_amount))

    def get_logging_by_user_id(self, user_id: str) -> list:
        """Получить все записи логов для пользователя"""
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM logging WHERE user_id = ? ORDER BY date DESC",
                (user_id,)
            ).fetchall()
            return result

    def get_logging_by_date(self, date: str) -> list:
        """Получить все записи логов за определённую дату"""
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM logging WHERE date LIKE ? ORDER BY date DESC",
                (f"%{date}%",)
            ).fetchall()
            return result

    def get_logging_all(self) -> list:
        """Получить все записи логов"""
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM logging ORDER BY date DESC"
            ).fetchall()
            return result

    def get_logging_by_id(self, log_id: int) -> tuple:
        """Получить запись лога по ID"""
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM logging WHERE id = ?",
                (log_id,)
            ).fetchone()
            return result

    def update_logging_fio(self, log_id: int, fio: str):
        """Обновить ФИО в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET fio = ? WHERE id = ?",
                (fio, log_id)
            )

    def update_logging_phone(self, log_id: int, phone: str):
        """Обновить телефон в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET phone = ? WHERE id = ?",
                (phone, log_id)
            )

    def update_logging_mood(self, log_id: int, mood: str):
        """Обновить настроение в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET mood = ? WHERE id = ?",
                (mood, log_id)
            )

    def update_logging_hungry(self, log_id: int, hungry: str):
        """Обновить уровень голода в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET hungry = ? WHERE id = ?",
                (hungry, log_id)
            )

    def update_logging_style(self, log_id: int, style: str):
        """Обновить стиль в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET style = ? WHERE id = ?",
                (style, log_id)
            )

    def update_logging_sex(self, log_id: int, sex: str):
        """Обновить пол в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET sex = ? WHERE id = ?",
                (sex, log_id)
            )

    def update_logging_age(self, log_id: int, age: str):
        """Обновить возраст в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET age = ? WHERE id = ?",
                (age, log_id)
            )

    def update_logging_dish_style(self, log_id: int, dish_style: str):
        """Обновить стиль блюд в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET dish_style = ? WHERE id = ?",
                (dish_style, log_id)
            )

    def update_logging_ccal(self, log_id: int, ccal: str):
        """Обновить калории в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET ccal = ? WHERE id = ?",
                (ccal, log_id)
            )

    def update_logging_dislike(self, log_id: int, dislike: str):
        """Обновить нелюбимые продукты в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET dislike = ? WHERE id = ?",
                (dislike, log_id)
            )

    def update_logging_like(self, log_id: int, like: str):
        """Обновить любимые продукты в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET like = ? WHERE id = ?",
                (like, log_id)
            )

    def update_logging_order(self, log_id: int, order_time: str):
        """Обновить время заказа в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET \"order\" = ? WHERE id = ?",
                (order_time, log_id)
            )

    def update_logging_sum(self, log_id: int, sum_amount: int):
        """Обновить сумму заказа в записи лога"""
        with self.connection:
            self.cursor.execute(
                "UPDATE logging SET sum = ? WHERE id = ?",
                (sum_amount, log_id)
            )

    def delete_logging_entry(self, log_id: int):
        """Удалить запись лога по ID"""
        with self.connection:
            self.cursor.execute(
                "DELETE FROM logging WHERE id = ?",
                (log_id,)
            )

    def get_logging_count(self) -> int:
        """Получить общее количество записей в логах"""
        with self.connection:
            result = self.connection.execute("SELECT COUNT(*) FROM logging").fetchone()
            return result[0]

    def get_logging_by_date_range(self, start_date: str, end_date: str) -> list:
        """Получить записи логов за период"""
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM logging WHERE date BETWEEN ? AND ? ORDER BY date DESC",
                (start_date, end_date)
            ).fetchall()
            return result

    # ======================================================================================================================
    # ===== УПРАВЛЕНИЕ СЕССИЯМИ ЛОГИРОВАНИЯ =================================================================================================
    # ======================================================================================================================

    def start_logging_session(self, user_id: str, date: str = None):
        """Начать новую сессию логирования"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Создаём новую запись с базовыми данными
        self.add_logging_entry(
            user_id=user_id,
            date=date,
            fio=None,
            phone=None,
            mood=None,
            hungry=None,
            style=None,
            sex=None,
            age=None,
            dish_style=None,
            ccal=None,
            dislike=None,
            like=None,
            order_time=None,
            sum_amount=None
        )

    def get_current_logging_session(self, user_id: str) -> tuple:
        """Получить текущую активную сессию пользователя (последнюю запись)"""
        with self.connection:
            result = self.connection.execute(
                "SELECT * FROM logging WHERE user_id = ? ORDER BY date DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            return result

    def update_logging_session_mood(self, user_id: str, mood: str):
        """Обновить настроение в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_mood(current_session[0], mood)

    def update_logging_session_hungry(self, user_id: str, hungry: str):
        """Обновить уровень голода в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_hungry(current_session[0], hungry)

    def update_logging_session_style(self, user_id: str, style: str):
        """Обновить стиль в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_style(current_session[0], style)

    def update_logging_session_sex(self, user_id: str, sex: str):
        """Обновить пол в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_sex(current_session[0], sex)

    def update_logging_session_age(self, user_id: str, age: str):
        """Обновить возраст в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_age(current_session[0], age)

    def update_logging_session_dish_style(self, user_id: str, dish_style: str):
        """Обновить стиль блюд в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_dish_style(current_session[0], dish_style)

    def update_logging_session_ccal(self, user_id: str, ccal: str):
        """Обновить калории в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_ccal(current_session[0], ccal)

    def update_logging_session_dislike(self, user_id: str, dislike: str):
        """Обновить нелюбимые продукты в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_dislike(current_session[0], dislike)

    def update_logging_session_like(self, user_id: str, like: str):
        """Обновить любимые продукты в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_like(current_session[0], like)

    def update_logging_session_order(self, user_id: str, order_composition: str = None):
        """Обновить состав заказа в текущей сессии"""
        if order_composition is None:
            order_composition = "Заказ не оформлен"

        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_order(current_session[0], order_composition)

    def update_logging_session_sum(self, user_id: str, sum_amount: int):
        """Обновить сумму заказа в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_sum(current_session[0], sum_amount)

    def update_logging_session_phone(self, user_id: str, phone: str):
        """Обновить телефон в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_phone(current_session[0], phone)

    def update_logging_session_fio(self, user_id: str, fio: str):
        """Обновить ФИО в текущей сессии"""
        current_session = self.get_current_logging_session(user_id)
        if current_session:
            self.update_logging_fio(current_session[0], fio)

    def get_dish_price_by_name(self, name):
        """Получение цены блюда по имени из новой БД (Menu.Price)"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT Price FROM Menu WHERE Name = ?",
                (name,)).fetchone()
        if result and result[0]:
            # Price хранится как TEXT, преобразуем в int
            try:
                return int(float(str(result[0])))
            except (ValueError, TypeError):
                return 0
        return 0

    # ======================================================================================================================
    # ===== ИСТОРИЯ ПРОФИЛЕЙ И ЗАКАЗОВ ====================================================================================
    # ======================================================================================================================

    def save_profile_history(self, user_id: int, change_source: str = 'api'):
        """Сохранение текущего профиля пользователя в историю.
        
        Args:
            user_id: ID пользователя
            change_source: Источник изменения ('api', 'bot', 'manual')
        """
        try:
            with self.connection:
                # Получаем текущий профиль
                profile = self.cursor.execute(
                    "SELECT phone, fio, age, sex, style, kcal, prefer, hate, mood, hungry, experiments, reviews, user_profile_json, menu_id FROM Profile WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
                
                if profile:
                    self.cursor.execute("""
                        INSERT INTO profile_history 
                        (user_id, phone, fio, age, sex, style, kcal, prefer, hate, mood, hungry, experiments, reviews, user_profile_json, menu_id, change_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        profile.get('phone'),
                        profile.get('fio'),
                        profile.get('age'),
                        profile.get('sex'),
                        profile.get('style'),
                        profile.get('kcal'),
                        profile.get('prefer'),
                        profile.get('hate'),
                        profile.get('mood'),
                        profile.get('hungry'),
                        profile.get('experiments'),
                        profile.get('reviews'),
                        profile.get('user_profile_json'),
                        profile.get('menu_id'),
                        change_source
                    ))
                    self.connection.commit()
                    print(f"✅ [HISTORY] Профиль user_id={user_id} сохранён в историю")
        except Exception as e:
            print(f"❌ [HISTORY] Ошибка сохранения профиля в историю: {e}")

    def save_order_history(self, user_id: int, basket: str = None, table_number: str = None, 
                          total_price: str = None, restaurant_name: str = None, 
                          menu_id: str = None, order_status: str = 'created', waiter_id: int = None):
        """Сохранение заказа в историю.
        
        Args:
            user_id: ID пользователя
            basket: Корзина в формате JSON
            table_number: Номер стола
            total_price: Сумма заказа
            restaurant_name: Название ресторана
            menu_id: ID меню
            order_status: Статус заказа ('created', 'confirmed', 'completed', 'cancelled')
            waiter_id: ID официанта, принявшего заказ
        """
        try:
            with self.connection:
                self.cursor.execute("""
                    INSERT INTO orders_history 
                    (user_id, basket, table_number, total_price, restaurant_name, menu_id, order_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, basket, table_number, total_price, restaurant_name, menu_id, order_status))
                self.connection.commit()
                print(f"✅ [HISTORY] Заказ user_id={user_id}, waiter_id={waiter_id} сохранён в историю (status={order_status})")
        except Exception as e:
            print(f"❌ [HISTORY] Ошибка сохранения заказа в историю: {e}")

    def get_profile_history(self, user_id: int, limit: int = 50) -> list:
        """Получение истории изменений профиля пользователя."""
        with self.connection:
            result = self.cursor.execute(
                "SELECT * FROM profile_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return result or []

    def get_order_history(self, user_id: int, limit: int = 50) -> list:
        """Получение истории заказов пользователя."""
        with self.connection:
            result = self.cursor.execute(
                "SELECT * FROM orders_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return result or []

    def get_all_orders_history(self, start_date: str = None, end_date: str = None, limit: int = 1000) -> list:
        """Получение всей истории заказов с опциональной фильтрацией по дате."""
        with self.connection:
            if start_date and end_date:
                result = self.cursor.execute(
                    "SELECT * FROM orders_history WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC LIMIT ?",
                    (start_date, end_date, limit)
                ).fetchall()
            else:
                result = self.cursor.execute(
                    "SELECT * FROM orders_history ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return result or []

    # ===== WAITER STATISTICS ================================================================================================

    def update_waiter_realtime_stats(self, waiter_id: int, order_amount: float, basket_json: str, client_id: int):
        """Обновление статистики официанта в реал-тайм при принятии заказа.
        
        Эта функция вызывается сразу после сохранения заказа и обновляет:
        - Счетчик заказов
        - Общую сумму и средний чек  
        - Список уникальных клиентов
        - Счетчики популярных блюд
        
        Args:
            waiter_id: ID официанта
            order_amount: Сумма заказа
            basket_json: JSON с корзиной заказа
            client_id: ID клиента
        """
        try:
            import json
            from datetime import datetime, timedelta
            
            # Определяем текущую неделю (понедельник - воскресенье)
            now = datetime.now()
            # Находим понедельник текущей недели
            days_since_monday = now.weekday()
            week_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7, microseconds=-1)
            
            with self.connection:
                # Проверяем, есть ли уже статистика за эту неделю
                existing = self.cursor.execute("""
                    SELECT id, orders_count, total_amount, unique_clients_count, popular_dishes_json
                    FROM waiter_statistics
                    WHERE waiter_id = ? AND period_start = ? AND period_end = ?
                """, (waiter_id, week_start, week_end)).fetchone()
                
                if existing:
                    # Обновляем существующую статистику
                    stat_id = existing[0]
                    orders_count = existing[1] + 1
                    total_amount = float(existing[2]) + float(order_amount)
                    avg_check = total_amount / orders_count
                    
                    # Получаем список уникальных клиентов за эту неделю
                    unique_clients = self.cursor.execute("""
                        SELECT COUNT(DISTINCT user_id)
                        FROM orders_history
                        WHERE waiter_id = ? AND created_at >= ? AND created_at < ?
                    """, (waiter_id, week_start, week_end)).fetchone()[0]
                    
                    # Обновляем популярные блюда
                    popular_dishes = json.loads(existing[4]) if existing[4] else []
                    popular_dishes = self._update_popular_dishes(popular_dishes, basket_json)
                    
                    # Обновляем запись
                    self.cursor.execute("""
                        UPDATE waiter_statistics
                        SET orders_count = ?,
                            total_amount = ?,
                            avg_check = ?,
                            unique_clients_count = ?,
                            popular_dishes_json = ?,
                            updated_at = NOW()
                        WHERE id = ?
                    """, (orders_count, total_amount, avg_check, unique_clients, json.dumps(popular_dishes, ensure_ascii=False), stat_id))
                    
                    self.connection.commit()
                    print(f"✅ [STATS] Обновлена статистика waiter_id={waiter_id}: {orders_count} заказов, {total_amount:.2f} руб.")
                    
                else:
                    # Создаем новую статистику
                    popular_dishes = self._update_popular_dishes([], basket_json)
                    
                    self.cursor.execute("""
                        INSERT INTO waiter_statistics
                        (waiter_id, period_start, period_end, orders_count, total_amount, avg_check, 
                         unique_clients_count, popular_dishes_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (waiter_id, week_start, week_end, 1, float(order_amount), float(order_amount), 
                          1, json.dumps(popular_dishes, ensure_ascii=False)))
                    
                    self.connection.commit()
                    print(f"✅ [STATS] Создана статистика waiter_id={waiter_id} за неделю {week_start.date()}")
                    
        except Exception as e:
            print(f"❌ [STATS] Ошибка обновления статистики: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_popular_dishes(self, popular_dishes: list, basket_json: str) -> list:
        """Обновляет список популярных блюд.
        
        Args:
            popular_dishes: Текущий список популярных блюд [{"dish_name": "...", "count": N}, ...]
            basket_json: JSON с корзиной заказа
            
        Returns:
            Обновленный список топ-5 популярных блюд
        """
        try:
            import json
            
            # Парсим корзину
            basket = json.loads(basket_json) if basket_json else {}
            
            # Создаем словарь для подсчета
            dishes_count = {}
            for dish in popular_dishes:
                dishes_count[dish['dish_name']] = dish['count']
            
            # Добавляем блюда из текущего заказа
            for dish_name, dish_data in basket.items():
                # dish_data может быть списком [dish_id, quantity] или другим форматом
                quantity = dish_data[1] if isinstance(dish_data, list) and len(dish_data) > 1 else 1
                dishes_count[dish_name] = dishes_count.get(dish_name, 0) + quantity
            
            # Сортируем и берем топ-5
            sorted_dishes = sorted(dishes_count.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return [{"dish_name": name, "count": count} for name, count in sorted_dishes]
            
        except Exception as e:
            print(f"⚠️ [STATS] Ошибка обновления популярных блюд: {e}")
            return popular_dishes
    
    def get_waiter_statistics_weekly(self, waiter_id: int):
        """Получение статистики официанта за текущую неделю.
        
        Args:
            waiter_id: ID официанта
            
        Returns:
            Словарь со статистикой или None
        """
        try:
            from datetime import datetime, timedelta
            
            now = datetime.now()
            days_since_monday = now.weekday()
            week_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7, microseconds=-1)
            
            result = self.cursor.execute("""
                SELECT waiter_id, period_start, period_end, orders_count, total_amount,
                       avg_check, unique_clients_count, popular_dishes_json
                FROM waiter_statistics
                WHERE waiter_id = ? AND period_start = ?
            """, (waiter_id, week_start)).fetchone()
            
            if result:
                return {
                    'waiter_id': result[0],
                    'period_start': result[1],
                    'period_end': result[2],
                    'orders_count': result[3],
                    'total_amount': float(result[4]),
                    'avg_check': float(result[5]),
                    'unique_clients_count': result[6],
                    'popular_dishes': result[7]
                }
            return None
            
        except Exception as e:
            print(f"❌ [STATS] Ошибка получения статистики: {e}")
            return None
    
    def get_waiter_statistics_period(self, waiter_id: int, start_date, end_date):
        """Получение статистики официанта за произвольный период.
        
        Args:
            waiter_id: ID официанта
            start_date: Начало периода (datetime)
            end_date: Конец периода (datetime)
            
        Returns:
            Список записей статистики
        """
        try:
            result = self.cursor.execute("""
                SELECT waiter_id, period_start, period_end, orders_count, total_amount,
                       avg_check, unique_clients_count, popular_dishes_json
                FROM waiter_statistics
                WHERE waiter_id = ? AND period_start >= ? AND period_end <= ?
                ORDER BY period_start DESC
            """, (waiter_id, start_date, end_date)).fetchall()
            
            return result or []
            
        except Exception as e:
            print(f"❌ [STATS] Ошибка получения статистики за период: {e}")
            return []
    
    def get_all_waiters_statistics(self, start_date=None, end_date=None):
        """Получение статистики по всем официантам за период.
        
        Args:
            start_date: Начало периода (опционально)
            end_date: Конец периода (опционально)
            
        Returns:
            Список записей статистики по всем официантам
        """
        try:
            if start_date and end_date:
                result = self.cursor.execute("""
                    SELECT waiter_id, SUM(orders_count) as total_orders, 
                           SUM(total_amount) as total_amount, AVG(avg_check) as avg_check
                    FROM waiter_statistics
                    WHERE period_start >= ? AND period_end <= ?
                    GROUP BY waiter_id
                    ORDER BY total_amount DESC
                """, (start_date, end_date)).fetchall()
            else:
                # Статистика за текущую неделю
                from datetime import datetime, timedelta
                now = datetime.now()
                days_since_monday = now.weekday()
                week_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                
                result = self.cursor.execute("""
                    SELECT waiter_id, orders_count, total_amount, avg_check
                    FROM waiter_statistics
                    WHERE period_start = ?
                    ORDER BY total_amount DESC
                """, (week_start,)).fetchall()
            
            return result or []
            
        except Exception as e:
            print(f"❌ [STATS] Ошибка получения статистики всех официантов: {e}")
            return []

    # ======================================================================================================================
    # ===== ТАБЛИЦА: iiko_keys =============================================================================================
    # ======================================================================================================================

    def get_iiko_key(self, restaurant_name: str):
        """Получить iiko API ключ для ресторана. Возвращает api_key или None."""
        try:
            with self.connection:
                result = self.cursor.execute(
                    "SELECT api_key FROM iiko_keys WHERE restaurant_name = ?",
                    (restaurant_name,)
                ).fetchone()
                if result:
                    return result[0]
                return None
        except Exception as e:
            print(f"❌ [IIKO] Ошибка получения ключа для '{restaurant_name}': {e}")
            return None

    def set_iiko_key(self, restaurant_name: str, api_key: str):
        """Установить или обновить iiko API ключ для ресторана."""
        try:
            with self.connection:
                self.cursor.execute(
                    """
                    INSERT INTO iiko_keys (restaurant_name, api_key)
                    VALUES (?, ?)
                    ON CONFLICT (restaurant_name) DO UPDATE SET api_key = EXCLUDED.api_key
                    """,
                    (restaurant_name, api_key)
                )
            print(f"✅ [IIKO] Ключ для '{restaurant_name}' успешно обновлен.")
            return True
        except Exception as e:
            print(f"❌ [IIKO] Ошибка установки ключа для '{restaurant_name}': {e}")
            return False

    def delete_iiko_key(self, restaurant_name: str):
        """Удалить iiko API ключ для ресторана."""
        try:
            with self.connection:
                self.cursor.execute(
                    "DELETE FROM iiko_keys WHERE restaurant_name = ?",
                    (restaurant_name,)
                )
            print(f"✅ [IIKO] Ключ для '{restaurant_name}' удален.")
            return True
        except Exception as e:
            print(f"❌ [IIKO] Ошибка удаления ключа для '{restaurant_name}': {e}")
            return False

    def get_iiko_id_by_dish_name(self, dish_name: str):
        """Получить iiko_id блюда по названию из таблицы menu. Возвращает iiko_id или None."""
        try:
            with self.connection:
                result = self.cursor.execute(
                    "SELECT iiko_id FROM menu WHERE name = ? AND iiko_id IS NOT NULL LIMIT 1",
                    (dish_name,)
                ).fetchone()
                if result:
                    return result[0]
                return None
        except Exception as e:
            print(f"❌ [IIKO] Ошибка получения iiko_id для '{dish_name}': {e}")
            return None

    def get_waiter_restaurant(self, waiter_id: int):
        """Получить ресторан официанта по waiter_id. Возвращает название или None."""
        try:
            with self.connection:
                result = self.cursor.execute(
                    "SELECT waiter_rest FROM waiters WHERE waiter_id = ?",
                    (waiter_id,)
                ).fetchone()
                if result and result[0]:
                    return result[0].split(':')[0]
                return None
        except Exception as e:
            print(f"❌ [IIKO] Ошибка получения ресторана для waiter_id={waiter_id}: {e}")
            return None

    def get_waiter_iiko_guid(self, waiter_id: int):
        """Получить GUID официанта в iiko (для плагина переназначения). Возвращает None если не привязан."""
        try:
            with self.connection:
                result = self.cursor.execute(
                    "SELECT iiko_guid FROM waiters WHERE waiter_id = ?",
                    (waiter_id,)
                ).fetchone()
                return result[0] if result and result[0] else None
        except Exception as e:
            print(f"❌ [IIKO] Ошибка получения iiko_guid для waiter_id={waiter_id}: {e}")
            return None

    # ======================================================================================================================
    # ===== ТАБЛИЦА: waiter_active_tables ==================================================================================
    # ======================================================================================================================

    def create_active_table(self, waiter_id: int, client_id: int, table_number: str, basket_json: str, total_price: int):
        """Создать или обновить запись активного стола и добавить гостя."""
        try:
            with self.connection:
                # Проверяем — может стол уже открыт этим официантом
                existing = self.cursor.execute(
                    "SELECT id FROM waiter_active_tables WHERE waiter_id = ? AND table_number = ? AND status = 'open'",
                    (waiter_id, table_number)
                ).fetchone()
                
                if existing:
                    table_id = existing[0]
                    self.cursor.execute(
                        "UPDATE waiter_active_tables SET basket_snapshot = ?, total_price = ?, client_id = ? WHERE id = ?",
                        (basket_json, total_price, client_id, table_id)
                    )
                else:
                    self.cursor.execute("""
                        INSERT INTO waiter_active_tables (waiter_id, client_id, table_number, basket_snapshot, total_price, status)
                        VALUES (?, ?, ?, ?, ?, 'open')
                        RETURNING id
                    """, (waiter_id, client_id, table_number, basket_json, total_price))
                    table_id = self.cursor.fetchone()[0]

                # Также добавляем/обновляем гостя в отдельной таблице
                self.add_guest_to_table(table_id, client_id, basket_json)
                
                self.connection.commit()
                print(f"✅ [TABLES] Стол {table_number} (id={table_id}) обновлен для waiter_id={waiter_id}")
                return table_id
        except Exception as e:
            print(f"❌ [TABLES] Ошибка создания активного стола: {e}")
            return None

    def add_guest_to_table(self, table_id: int, client_id: int, basket_json: str = '{}', name: str = None, guest_number: int = None):
        """Привязать гостя к активному столу."""
        try:
            existing = self.cursor.execute(
                "SELECT id FROM waiter_active_table_guests WHERE active_table_id = ? AND client_id = ?",
                (table_id, client_id)
            ).fetchone()
            
            if existing:
                self.cursor.execute(
                    "UPDATE waiter_active_table_guests SET basket_snapshot = ?, name = COALESCE(?, name), guest_number = COALESCE(?, guest_number) WHERE id = ?",
                    (basket_json, name, guest_number, existing[0])
                )
            else:
                self.cursor.execute("""
                    INSERT INTO waiter_active_table_guests (active_table_id, client_id, basket_snapshot, name, guest_number)
                    VALUES (?, ?, ?, ?, ?)
                """, (table_id, client_id, basket_json, name, guest_number))
            return True
        except Exception as e:
            print(f"❌ [TABLES] Ошибка добавления гостя к столу: {e}")
            return False

    def get_table_guests(self, table_id: int) -> list:
        """Получить всех гостей привязанных к столу."""
        try:
            result = self.cursor.execute("""
                SELECT id, client_id, basket_snapshot, name, created_at, guest_number
                FROM waiter_active_table_guests
                WHERE active_table_id = ?
                ORDER BY guest_number ASC, created_at ASC
            """, (table_id,)).fetchall()
            return result or []
        except Exception as e:
            print(f"❌ [TABLES] Ошибка получения гостей стола: {e}")
            return []


    def get_active_tables(self, waiter_id: int) -> list:
        """Получить список открытых столов официанта."""
        try:
            with self.connection:
                result = self.cursor.execute("""
                    SELECT id, waiter_id, client_id, table_number, basket_snapshot, total_price, created_at, iiko_table_id
                    FROM waiter_active_tables
                    WHERE waiter_id = ? AND status = 'open'
                    ORDER BY created_at DESC
                """, (waiter_id,)).fetchall()
                return result or []
        except Exception as e:
            print(f"❌ [TABLES] Ошибка получения активных столов: {e}")
            return []

    def close_active_table(self, table_id: int):
        """Закрыть стол (по ID записи)."""
        try:
            with self.connection:
                self.cursor.execute(
                    "UPDATE waiter_active_tables SET status = 'closed', closed_at = NOW() WHERE id = ?",
                    (table_id,)
                )
                self.connection.commit()
                print(f"✅ [TABLES] Стол id={table_id} закрыт")
        except Exception as e:
            print(f"❌ [TABLES] Ошибка закрытия стола: {e}")

    def close_active_table_by_number(self, waiter_id: int, table_number: str):
        """Закрыть стол по номеру стола и waiter_id."""
        try:
            with self.connection:
                self.cursor.execute(
                    "UPDATE waiter_active_tables SET status = 'closed', closed_at = NOW() WHERE waiter_id = ? AND table_number = ? AND status = 'open'",
                    (waiter_id, table_number)
                )
                self.connection.commit()
                print(f"✅ [TABLES] Стол {table_number} для waiter_id={waiter_id} закрыт")
        except Exception as e:
            print(f"❌ [TABLES] Ошибка закрытия стола: {e}")


    # ======================================================================================================================
    # ===== DATAWAVE ===============================================================================================
    # ======================================================================================================================

    def get_user_phone_dw(self, user_id):
        with self.connection:
            result = self.cursor.execute(
                "SELECT phone FROM profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            return result[0] if result else None

    def get_user_name_dw(self, user_id):
        with self.connection:
            result = self.cursor.execute(
                "SELECT fio FROM profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            return result[0] if result else None

    def get_user_diets_dw(self, user_id):
        with self.connection:
            result = self.cursor.execute(
                "SELECT prefer FROM profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            return result[0] if result else None

    def get_user_hate_dw(self, user_id):
        with self.connection:
            result = self.cursor.execute(
                "SELECT hate FROM profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            return result[0] if result else None

    def get_user_order_items_dw(self, user_id):
        import json as _json
        with self.connection:
            rows = self.cursor.execute(
                "SELECT basket FROM orders_history WHERE user_id = ?",
                (user_id,)
            ).fetchall()
        dishes = set()
        for row in rows:
            if row[0]:
                try:
                    basket_data = _json.loads(row[0])
                    dishes.update(basket_data.keys())
                except Exception:
                    continue
        return list(dishes)

    def build_datawave_dict(self, user_id):
        return {
            "Phone": self.get_user_phone_dw(user_id),
            "User Name": self.get_user_name_dw(user_id),
            "Diets": self.get_user_diets_dw(user_id),
            "Hate": self.get_user_hate_dw(user_id),
            "Cart Items": self.get_user_order_items_dw(user_id),
        }




    def get_users_for_datawave(self):
        """Метод для получения всех несинхронизированных пользователей"""
        try:
            self.cursor.execute("""
                SELECT user_id, phone, fio, prefer, hate 
                FROM profile 
                WHERE is_synced = FALSE 
                AND phone IS NOT NULL 
                AND phone != ''
            """)
            rows = self.cursor.fetchall()
            
            users = []
            for row in rows:
                # Формируем словарь, который ожидает sync_all_pending_users
                users.append({
                    "Phone": row.get("phone"),
                    "User Name": row.get("fio"),
                    "Diets": row.get("prefer") if isinstance(row.get("prefer"), list) else [],
                    "Hate": row.get("hate") if isinstance(row.get("hate"), list) else [],
                    "Cart Items": []
                })
            return users
        except Exception as e:
            print(f"[DB] Ошибка получения юзеров для DataWave: {e}")
            return []

    def mark_as_synced(self, phones_list):
        """Пометка пользователей как синхронизированных"""
        if not phones_list:
            return True
        try:
            placeholders = ", ".join(["%s"] * len(phones_list))
            sql = f"UPDATE profile SET is_synced = 'yes' WHERE phone IN ({placeholders})"
            self.cursor.execute(sql, tuple(phones_list))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"[DB] Ошибка обновления статуса синхронизации: {e}")
            return False



    # ======================================================================================================================
    # ===== ОТЗЫВЫ ===============================================================================================
    # ======================================================================================================================

    def save_feedback(self, feedback_data):
        """
        Сохраняет отзыв в таблицу feedback.
        feedback_data: объект Pydantic-модели FeedbackCreate из api/models.py
        """
        with self.connection:
            query = """
                INSERT INTO feedback (user_id, dish_id, order_id, rating, comment)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id;
            """
        
            result = self.cursor.execute(query, (
                feedback_data.user_id,
                feedback_data.dish_id,
                feedback_data.order_id,
                feedback_data.rating,
                feedback_data.comment
            )).fetchone()
            

            return result[0] if result else None
