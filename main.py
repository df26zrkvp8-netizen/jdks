"""
![⚠️](tg://emoji?id=5839402707751805527) ДАННЫЙ КОД ПРЕДОСТАВЛЕН В ОБРАЗОВАТЕЛЬНЫХ ЦЕЛЯХ.
Запуск бота — ваша ответственность.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================================================
# НАСТРОЙКИ
# ============================================================
BOT_TOKEN = "8997689824:AAGZa03iSkHuN-iq9Q_mwCdlYDYp2i102hY"          # @BotFather
ADMIN_IDS = [7216439072]    # ваши Telegram ID
DB_NAME = "shop.db"
CURRENCY = "₴"                        # гривна
BOT_USERNAME = "example_bot"          # юзернейм бота

logging.basicConfig(level=logging.INFO)

# ============================================================
# БАЗА ДАННЫХ (SQLite)
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            visible INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            visible INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            visible INTEGER DEFAULT 1,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS city_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            city_id INTEGER NOT NULL,
            price INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (city_id) REFERENCES cities(id),
            UNIQUE(product_id, city_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            city_id INTEGER,
            city_name TEXT,
            items TEXT,
            total INTEGER,
            contact TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            banned INTEGER DEFAULT 0,
            registered_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ БД
# ============================================================
def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone:
        res = c.fetchone()
    elif fetchall:
        res = c.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return res

# ----- ГОРОДА -----
def get_cities(visible_only=True):
    q = "SELECT id, name FROM cities WHERE visible=1 ORDER BY name" if visible_only else "SELECT id, name FROM cities ORDER BY name"
    return db_query(q, fetchall=True)

def add_city(name):
    try:
        db_query("INSERT INTO cities (name) VALUES (?)", (name,), commit=True)
        return True
    except sqlite3.IntegrityError:
        return False

def del_city(city_id):
    db_query("UPDATE cities SET visible=0 WHERE id=?", (city_id,), commit=True)

# ----- КАТЕГОРИИ -----
def get_categories(visible_only=True):
    q = "SELECT id, name FROM categories WHERE visible=1 ORDER BY name" if visible_only else "SELECT id, name FROM categories ORDER BY name"
    return db_query(q, fetchall=True)

def add_category(name):
    try:
        db_query("INSERT INTO categories (name) VALUES (?)", (name,), commit=True)
        return True
    except sqlite3.IntegrityError:
        return False

def del_category(cat_id):
    db_query("UPDATE categories SET visible=0 WHERE id=?", (cat_id,), commit=True)

# ----- ТОВАРЫ -----
def get_products(category_id=None, visible_only=True):
    if category_id:
        q = "SELECT id, name, price FROM products WHERE category_id=? AND visible=1 ORDER BY name" if visible_only else "SELECT id, name, price FROM products WHERE category_id=? ORDER BY name"
        return db_query(q, (category_id,), fetchall=True)
    else:
        q = "SELECT id, name, price FROM products WHERE visible=1 ORDER BY name" if visible_only else "SELECT id, name, price FROM products ORDER BY name"
        return db_query(q, fetchall=True)

def add_product(category_id, name, price):
    db_query("INSERT INTO products (category_id, name, price) VALUES (?,?,?)", (category_id, name, price), commit=True)

def del_product(prod_id):
    db_query("UPDATE products SET visible=0 WHERE id=?", (prod_id,), commit=True)

def update_product_price(prod_id, price):
    db_query("UPDATE products SET price=? WHERE id=?", (price, prod_id), commit=True)

# ----- ЦЕНЫ ПО ГОРОДАМ -----
def get_city_price(product_id, city_id):
    r = db_query("SELECT price FROM city_prices WHERE product_id=? AND city_id=?", (product_id, city_id), fetchone=True)
    return r[0] if r else None

def set_city_price(product_id, city_id, price):
    db_query("INSERT OR REPLACE INTO city_prices (product_id, city_id, price) VALUES (?,?,?)", (product_id, city_id, price), commit=True)

def del_city_price(product_id, city_id):
    db_query("DELETE FROM city_prices WHERE product_id=? AND city_id=?", (product_id, city_id), commit=True)

# ----- ЗАКАЗЫ -----
def get_orders(status=None, limit=50):
    if status:
        return db_query("SELECT * FROM orders WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit), fetchall=True)
    return db_query("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,), fetchall=True)

def set_order_status(order_id, status):
    db_query("UPDATE orders SET status=? WHERE id=?", (status, order_id), commit=True)

# ----- ПОЛЬЗОВАТЕЛИ -----
def register_user(message: types.Message):
    uid = message.from_user.id
    u = db_query("SELECT user_id FROM users WHERE user_id=?", (uid,), fetchone=True)
    if not u:
        db_query(
            "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?,?,?,?)",
            (uid, message.from_user.username, message.from_user.first_name, message.from_user.last_name),
            commit=True
        )

def is_banned(user_id):
    r = db_query("SELECT banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
    return r and r[0] == 1

# ============================================================
# КЛАВИАТУРЫ
# ============================================================
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Каталог", callback_data="catalog")
    kb.button(text="📦 Корзина", callback_data="cart")
    kb.button(text="![📞](tg://emoji?id=6016903402468940975) Контакты", callback_data="contacts")
    kb.button(text="![ℹ️](tg://emoji?id=5837012025875636594) О нас", callback_data="about")
    kb.adjust(2)
    return kb.as_markup()

def back_button(cb="menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data=cb)]
    ])

def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏙️ Города", callback_data="admin_cities")
    kb.button(text="![📂](tg://emoji?id=6016954581299240060) Категории", callback_data="admin_categories")
    kb.button(text="📦 Товары", callback_data="admin_products")
    kb.button(text="![💰](tg://emoji?id=5816499429573664347) Цены по городам", callback_data="admin_city_prices")
    kb.button(text="📋 Заказы", callback_data="admin_orders")
    kb.button(text="![👥](tg://emoji?id=6017207340124611376) Юзеры", callback_data="admin_users")
    kb.button(text="🔙 Выход", callback_data="menu")
    kb.adjust(2)
    return kb.as_markup()

# ============================================================
# FSM СОСТОЯНИЯ
# ============================================================
class AdminStates(StatesGroup):
    # города
    city_add = State()
    city_del = State()
    # категории
    cat_add = State()
    cat_del = State()
    # товары
    prod_add_name = State()
    prod_add_price = State()
    prod_del = State()
    prod_edit_price = State()
    # цены по городам
    cp_select_product = State()
    cp_select_city = State()
    cp_set_price = State()
    cp_del = State()
    # заказы
    order_status = State()

class UserStates(StatesGroup):
    cart = State()
    order_city = State()
    order_contact = State()
    order_confirm = State()

# ============================================================
# ИНИЦИАЛИЗАЦИЯ БОТА
# ============================================================
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ============================================================
# ФИЛЬТРЫ
# ============================================================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ============================================================
# КОМАНДЫ
# ============================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    register_user(message)
    if is_banned(message.from_user.id):
        return await message.answer("![❌](tg://emoji?id=5837071708741183799) Вы заблокированы.")
    await message.answer(
        f"👋 Добро пожаловать!\n\n"
        f"Используй кнопки ниже для навигации.",
        reply_markup=main_menu()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("![🔐](tg://emoji?id=6016876125131643723) Панель администратора:", reply_markup=admin_menu())

# ============================================================
# ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ
# ============================================================
@dp.callback_query(F.data == "menu")
async def back_menu(call: types.CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()

@dp.callback_query(F.data == "catalog")
async def catalog_categories(call: types.CallbackQuery):
    cats = get_categories()
    if not cats:
        return await call.message.edit_text("Каталог пуст.", reply_markup=back_button())
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=c[1], callback_data=f"cat_{c[0]}")
    kb.button(text="← Назад", callback_data="menu")
    kb.adjust(2)
    await call.message.edit_text("![📂](tg://emoji?id=6016954581299240060) Выбери категорию:", reply_markup=kb.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def catalog_products(call: types.CallbackQuery):
    cat_id = int(call.data.split("_")[1])
    prods = get_products(cat_id)
    if not prods:
        return await call.message.edit_text("В этой категории пока ничего нет.", reply_markup=back_button("catalog"))
    kb = InlineKeyboardBuilder()
    for p in prods:
        kb.button(text=f"{p[1]} — {p[2]}{CURRENCY}", callback_data=f"prod_{p[0]}")
    kb.button(text="← Назад", callback_data="catalog")
    kb.adjust(1)
    await call.message.edit_text("Выбери товар:", reply_markup=kb.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("prod_"))
async def product_detail(call: types.CallbackQuery):
    pid = int(call.data.split("_")[1])
    p = db_query("SELECT name, price FROM products WHERE id=?", (pid,), fetchone=True)
    if not p:
        return await call.message.edit_text("Товар не найден.", reply_markup=back_button("catalog"))
    cities = get_cities()
    kb = InlineKeyboardBuilder()
    for city in cities:
        # проверим индивидуальную цену
        cp = get_city_price(pid, city[0])
        price_str = f"{cp}{CURRENCY}" if cp else f"{p[1]}{CURRENCY}"
        kb.button(text=f"{city[1]} — {price_str}", callback_data=f"order_{pid}_{city[0]}")
    kb.button(text="← Назад", callback_data="catalog")
    kb.adjust(1)
    await call.message.edit_text(
        f"📦 {p[0]}\nБазовая цена: {p[1]}{CURRENCY}\n\nВыбери город для заказа:",
        reply_markup=kb.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("order_"))
async def start_order(call: types.CallbackQuery, state: FSMContext):
    _, pid, cid = call.data.split("_")
    pid, cid = int(pid), int(cid)
    p = db_query("SELECT name, price FROM products WHERE id=?", (pid,), fetchone=True)
    city = db_query("SELECT name FROM cities WHERE id=?", (cid,), fetchone=True)
    cp = get_city_price(pid, cid)
    final_price = cp if cp else p[1]
    await state.update_data(
        product_id=pid, product_name=p[0], base_price=p[1],
        city_id=cid, city_name=city[0], final_price=final_price
    )
    await call.message.edit_text(
        f"Товар: {p[0]}\nГород: {city[0]}\nЦена: {final_price}{CURRENCY}\n\n"
        f"Введи свой контакт (телефон / @username) для связи:",
        reply_markup=back_button("catalog")
    )
    await state.set_state(UserStates.order_contact)
    await call.answer()

@dp.message(UserStates.order_contact)
async def order_contact_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(contact=message.text)
    # создаём заказ
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO orders (user_id, username, city_id, city_name, items, total, contact) VALUES (?,?,?,?,?,?,?)",
        (message.from_user.id, message.from_user.username,
         data['city_id'], data['city_name'],
         data['product_name'], data['final_price'], message.text)
    )
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    await message.answer(
        f"![✅](tg://emoji?id=5836754134564347425) Заказ #{order_id} создан!\n\n"
        f"Товар: {data['product_name']}\n"
        f"Город: {data['city_name']}\n"
        f"Сумма: {data['final_price']}{CURRENCY}\n"
        f"Контакт: {message.text}\n\n"
        f"Ожидайте подтверждения оператора.",
        reply_markup=main_menu()
    )
    await state.clear()

@dp.callback_query(F.data == "cart")
async def cart_info(call: types.CallbackQuery):
    # упрощённо — показываем последние заказы пользователя
    orders = db_query(
        "SELECT id, items, total, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5",
        (call.from_user.id,), fetchall=True
    )
    if not orders:
        return await call.message.edit_text("У тебя пока нет заказов.", reply_markup=back_button())
    text = "📋 Твои последние заказы:\n\n"
    for o in orders:
        text += f"#{o[0]} {o[1]} — {o[2]}{CURRENCY} [{o[3]}]\n   {o[4]}\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()
    @dp.callback_query(F.data == "contacts")
async def show_contacts(call: types.CallbackQuery):
    await call.message.edit_text(
        "![📞](tg://emoji?id=6016903402468940975) Связь с оператором:\n@operator_username\n\n"
        "Или пиши в личку — ответим в ближайшее время.",
        reply_markup=back_button()
    )
    await call.answer()

@dp.callback_query(F.data == "about")
async def show_about(call: types.CallbackQuery):
    await call.message.edit_text(
        "![ℹ️](tg://emoji?id=5839428533390154876) О нас\n\n"
        "Магазин работает по всей Украине.\n"
        "Анонимно. Быстрая доставка.\n"
        "Оплата при получении.\n\n"
        "По всем вопросам — @operator_username",
        reply_markup=back_button()
    )
    await call.answer()

# ============================================================
# АДМИН-ПАНЕЛЬ
# ============================================================
@dp.callback_query(F.data.startswith("admin_"))
async def admin_handler(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    action = call.data.split("_", 1)[1]

    # ----- ГОРОДА -----
    if action == "cities":
        cities = get_cities(visible_only=False)
        text = "🏙️ Города:\n\n"
        kb = InlineKeyboardBuilder()
        for c in cities:
            text += f"#{c[0]} {c[1]}\n"
            kb.button(text=f"![❌](tg://emoji?id=5837071708741183799) {c[1]}", callback_data=f"city_del_{c[0]}")
        text += "\n![➕](tg://emoji?id=6017367830167559319) Добавить новый город"
        kb.button(text="![➕](tg://emoji?id=6017367830167559319) Добавить", callback_data="city_add")
        kb.button(text="🔙 Назад", callback_data="menu_admin")
        kb.adjust(2)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action == "city_add":
        await call.message.edit_text("Введи название города:")
        await state.set_state(AdminStates.city_add)
        await call.answer()

    elif action.startswith("city_del_"):
        cid = int(action.split("_")[2])
        del_city(cid)
        await call.message.edit_text("![✅](tg://emoji?id=5836754134564347425) Город удалён.", reply_markup=back_button("admin_cities"))
        await call.answer()

    # ----- КАТЕГОРИИ -----
    elif action == "categories":
        cats = get_categories(visible_only=False)
        text = "![📂](tg://emoji?id=6016954581299240060) Категории:\n\n"
        kb = InlineKeyboardBuilder()
        for c in cats:
            text += f"#{c[0]} {c[1]}\n"
            kb.button(text=f"![❌](tg://emoji?id=5837071708741183799) {c[1]}", callback_data=f"cat_del_{c[0]}")
        kb.button(text="![➕](tg://emoji?id=6017367830167559319) Добавить", callback_data="cat_add")
        kb.button(text="🔙 Назад", callback_data="menu_admin")
        kb.adjust(2)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action == "cat_add":
        await call.message.edit_text("Введи название категории:")
        await state.set_state(AdminStates.cat_add)
        await call.answer()

    elif action.startswith("cat_del_"):
        cid = int(action.split("_")[2])
        del_category(cid)
        await call.message.edit_text("![✅](tg://emoji?id=6016835129668803369) Категория удалена.", reply_markup=back_button("admin_categories"))
        await call.answer()

    # ----- ТОВАРЫ -----
    elif action == "products":
        prods = get_products(visible_only=False)
        text = "📦 Товары:\n\n"
        kb = InlineKeyboardBuilder()
        for p in prods:
            text += f"#{p[0]} {p[1]} — {p[2]}{CURRENCY}\n"
            kb.button(text=f"![✏️](tg://emoji?id=5841424104044896686) {p[1]}", callback_data=f"prod_edit_{p[0]}")
            kb.button(text=f"![❌](tg://emoji?id=5837071708741183799) {p[1]}", callback_data=f"prod_del_{p[0]}")
        kb.button(text="![➕](tg://emoji?id=6017367830167559319) Добавить", callback_data="prod_add")
        kb.button(text="🔙 Назад", callback_data="menu_admin")
        kb.adjust(2)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action == "prod_add":
        cats = get_categories()
        if not cats:
            return await call.message.edit_text("Сначала создай категорию.", reply_markup=back_button("admin_products"))
        kb = InlineKeyboardBuilder()
        for c in cats:
            kb.button(text=c[1], callback_data=f"prod_add_cat_{c[0]}")
        kb.button(text="← Назад", callback_data="admin_products")
        kb.adjust(1)
        await call.message.edit_text("Выбери категорию для нового товара:", reply_markup=kb.as_markup())
        await call.answer()

    elif action.startswith("prod_add_cat_"):
        cat_id = int(action.split("_")[3])
        await state.update_data(prod_cat_id=cat_id)
        await call.message.edit_text("Введи название товара:")
        await state.set_state(AdminStates.prod_add_name)
        await call.answer()

    elif action.startswith("prod_del_"):
        pid = int(action.split("_")[2])
        del_product(pid)
        await call.message.edit_text("![✅](tg://emoji?id=5839438557843824209) Товар удалён.", reply_markup=back_button("admin_products"))
        await call.answer()

    elif action.startswith("prod_edit_"):
        pid = int(action.split("_")[2])
        p = db_query("SELECT name, price FROM products WHERE id=?", (pid,), fetchone=True)
        await state.update_data(edit_prod_id=pid)
        kb = InlineKeyboardBuilder()
        kb.button(text="![💰](tg://emoji?id=5816499429573664347) Изменить цену", callback_data=f"prod_edit_price_{pid}")
        kb.button(text="← Назад", callback_data="admin_products")
        await call.message.edit_text(
            f"Редактирование: {p[0]}\nТекущая цена: {p[1]}{CURRENCY}",
            reply_markup=kb.as_markup()
        )
        await call.answer()

    elif action.startswith("prod_edit_price_"):
        pid = int(action.split("_")[3])
        await state.update_data(edit_prod_id=pid)
        await call.message.edit_text("Введи новую цену (только цифры):")
        await state.set_state(AdminStates.prod_edit_price)
        await call.answer()

    # ----- ЦЕНЫ ПО ГОРОДАМ -----
    elif action == "city_prices":
        prods = get_products()
        if not prods:
            return await call.message.edit_text("Нет товаров.", reply_markup=back_button("menu_admin"))
        text = "![💰](tg://emoji?id=5816499429573664347) Цены по городам\n\nВыбери товар:\n"
        kb = InlineKeyboardBuilder()
        for p in prods:
            kb.button(text=f"{p[1]} ({p[2]}{CURRENCY})", callback_data=f"cp_prod_{p[0]}")
        kb.button(text="🔙 Назад", callback_data="menu_admin")
        kb.adjust(1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action.startswith("cp_prod_"):
        pid = int(action.split("_")[2])
        await state.update_data(cp_prod_id=pid)
        cities = get_cities()
        if not cities:
            return await call.message.edit_text("Нет городов.", reply_markup=back_button("admin_city_prices"))
        text = "Выбери город:\n"
        kb = InlineKeyboardBuilder()
        for c in cities:
            cur = get_city_price(pid, c[0])
            cur_str = f" ({cur}{CURRENCY})" if cur else ""
            kb.button(text=f"{c[1]}{cur_str}", callback_data=f"cp_city_{c[0]}")
        kb.button(text="← Назад", callback_data="admin_city_prices")
        kb.adjust(1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action.startswith("cp_city_"):
        cid = int(action.split("_")[2])
        await state.update_data(cp_city_id=cid)
        data = await state.get_data()
        pid = data['cp_prod_id']
        cur = get_city_price(pid, cid)
        kb = InlineKeyboardBuilder()
        kb.button(text="![💰](tg://emoji?id=5816499429573664347) Установить цену", callback_data="cp_set")
        if cur:
            kb.button(text="![❌](tg://emoji?id=5837071708741183799) Удалить цену", callback_data="cp_del")
        kb.button(text="← Назад", callback_data=f"cp_prod_{pid}")
        await call.message.edit_text(
            f"Текущая цена для этого города: {cur if cur else 'не установлена'}{CURRENCY}\n\n"
            f"Базовая цена товара: {db_query('SELECT price FROM products WHERE id=?', (pid,), fetchone=True)[0]}{CURRENCY}",
            reply_markup=kb.as_markup()
        )
        await call.answer()

    elif action == "cp_set":
        await call.message.edit_text("Введи цену для этого города (только цифры):")
        await state.set_state(AdminStates.cp_set_price)
        await call.answer()

    elif action == "cp_del":
        data = await state.get_data()
        del_city_price(data['cp_prod_id'], data['cp_city_id'])
        await call.message.edit_text("![✅](tg://emoji?id=5836754134564347425) Цена удалена.", reply_markup=back_button(f"cp_prod_{data['cp_prod_id']}"))
        await call.answer()

    # ----- ЗАКАЗЫ -----
    elif action == "orders":
        orders = get_orders()
        if not orders:
            return await call.message.edit_text("Нет заказов.", reply_markup=back_button("menu_admin"))
        text = "📋 Заказы:\n\n"
        kb = InlineKeyboardBuilder()
        for o in orders:
            text += f"#{o[0]} | {o[5]} | {o[7]} | {o[6]}{CURRENCY} | {o[8]}\n"
            kb.button(text=f"#{o[0]} — {o[7]}", callback_data=f"order_view_{o[0]}")
        kb.button(text="🔙 Назад", callback_data="menu_admin")
        kb.adjust(1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action.startswith("order_view_"):
        oid = int(action.split("_")[2])
        o = db_query("SELECT * FROM orders WHERE id=?", (oid,), fetchone=True)
        if not o:
            return await call.message.edit_text("Заказ не найден.", reply_markup=back_button("admin_orders"))
        kb = InlineKeyboardBuilder()
        status_map = {"new": "![✅](tg://emoji?id=5839438557843824209) Подтвердить", "confirmed": "📦 Отправить", "shipped": "![✅](tg://emoji?id=5839438557843824209) Завершить"}
        if o[8] in status_map:
            kb.button(text=status_map[o[8]], callback_data=f"order_status_{o[0]}_{o[8]}")
        kb.button(text="![❌](tg://emoji?id=5837071708741183799) Отменить", callback_data=f"order_cancel_{o[0]}")
        kb.button(text="← Назад", callback_data="admin_orders")
        kb.adjust(1)
        await call.message.edit_text(
            f"📋 Заказ #{o[0]}\n"
            f"Товар: {o[5]}\n"
            f"Город: {o[4]}\n"
            f"Сумма: {o[6]}{CURRENCY}\n"
            f"Контакт: {o[7]}\n"
            f"Статус: {o[8]}\n"
            f"Дата: {o[9]}\n"
            f"Пользователь: @{o[2] if o[2] else o[1]}",
            reply_markup=kb.as_markup()
        )
        await call.answer()

    elif action.startswith("order_status_"):
        parts = action.split("_")
        oid = int(parts[2])
        cur_status = parts[3]
        next_status = {"new": "confirmed", "confirmed": "shipped", "shipped": "done"}
        if cur_status in next_status:
            set_order_status(oid, next_status[cur_status])
        await call.message.edit_text(f"![✅](tg://emoji?id=5836754134564347425) Статус обновлён.", reply_markup=back_button("admin_orders"))
        await call.answer()

    elif action.startswith("order_cancel_"):
        oid = int(action.split("_")[2])
        set_order_status(oid, "cancelled")
        await call.message.edit_text("![❌](tg://emoji?id=5837071708741183799) Заказ отменён.", reply_markup=back_button("admin_orders"))
        await call.answer()

    # ----- ЮЗЕРЫ -----
    elif action == "users":
        users = db_query("SELECT user_id, username, first_name, banned FROM users ORDER BY registered_at DESC LIMIT 50", fetchall=True)
        text = "![👥](tg://emoji?id=5839351498856733854) Пользователи:\n\n"
        kb = InlineKeyboardBuilder()
        for u in users:
            status = "![🚫](tg://emoji?id=6017042035423321562)" if u[3] else "![✅](tg://emoji?id=6016835129668803369)"
            text += f"{status} {u[0]} @{u[1]} {u[2]}\n"
            if not u[3]:
                kb.button(text=f"![🚫](tg://emoji?id=5836669502233780114) Забанить {u[0]}", callback_data=f"ban_{u[0]}")
            else:
                kb.button(text=f"![✅](tg://emoji?id=5839438557843824209) Разбанить {u[0]}", callback_data=f"unban_{u[0]}")
        kb.button(text="🔙 Назад", callback_data="menu_admin")
        kb.adjust(1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()

    elif action.startswith("ban_"):
        uid = int(action.split("_")[1])
        db_query("UPDATE users SET banned=1 WHERE user_id=?", (uid,), commit=True)
        await call.message.edit_text("![✅](tg://emoji?id=5816434549797690254) Пользователь забанен.", reply_markup=back_button("admin_users"))
        await call.answer()

    elif action.startswith("unban_"):
        uid = int(action.split("_")[1])
        db_query("UPDATE users SET banned=0 WHERE user_id=?", (uid,), commit=True)
        await call.message.edit_text("![✅](tg://emoji?id=5839438557843824209) Пользователь разбанен.", reply_markup=back_button("admin_users"))
        await call.answer()

    else:
        await call.answer()

# ----- ВОЗВРАТ В АДМИН-МЕНЮ -----
@dp.callback_query(F.data == "menu_admin")
async def back_admin(call: types.CallbackQuery):
    await call.message.edit_text("![🔐](tg://emoji?id=6016876125131643723) Панель администратора:", reply_markup=admin_menu())
    await call.answer()

# ============================================================
# ОБРАБОТЧИКИ СОСТОЯНИЙ (FSM)
# ============================================================
@dp.message(AdminStates.city_add)
async def city_add_done(message: types.Message, state: FSMContext):
    if add_city(message.text.strip()):
        await message.answer(f"![✅](tg://emoji?id=5839438557843824209) Город «{message.text}» добавлен.", reply_markup=admin_menu())
    else:
        await message.answer("![❌](tg://emoji?id=5837071708741183799) Такой город уже есть.", reply_markup=admin_menu())
    await state.clear()

@dp.message(AdminStates.cat_add)
async def cat_add_done(message: types.Message, state: FSMContext):
    if add_category(message.text.strip()):
        await message.answer(f"![✅](tg://emoji?id=5839438557843824209) Категория «{message.text}» добавлена.", reply_markup=admin_menu())
    else:
        await message.answer("![❌](tg://emoji?id=5837071708741183799) Такая категория уже есть.", reply_markup=admin_menu())
    await state.clear()

@dp.message(AdminStates.prod_add_name)
async def prod_add_name_done(message: types.Message, state: FSMContext):
    await state.update_data(prod_name=message.text.strip())
    await message.answer("Введи цену товара (только цифры):")
    await state.set_state(AdminStates.prod_add_price)

@dp.message(AdminStates.prod_add_price)
async def prod_add_price_done(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("![❌](tg://emoji?id=5837071708741183799) Введи число.")
    data = await state.get_data()
    add_product(data['prod_cat_id'], data['prod_name'], int(message.text))
    await message.answer(f"![✅](tg://emoji?id=6016835129668803369) Товар «{data['prod_name']}» добавлен.", reply_markup=admin_menu())
    await state.clear()

@dp.message(AdminStates.prod_edit_price)
async def prod_edit_price_done(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("![❌](tg://emoji?id=5837071708741183799) Введи число.")
    data = await state.get_data()
    update_product_price(data['edit_prod_id'], int(message.text))
    await message.answer("![✅](tg://emoji?id=5839438557843824209) Цена обновлена.", reply_markup

