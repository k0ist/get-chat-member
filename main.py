import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv  # <-- Импортируем библиотеку для работы с .env

# Инициализация логов
logging.basicConfig(level=logging.INFO)

# Загружаем переменные строго из файла keys.env
# override=True гарантирует, что локальные значения перезапишут системные при локальном тесте
load_dotenv(dotenv_path="keys.env", override=True)

# Теперь os.getenv считает данные из keys.env
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")
RENDER_URL = os.getenv("RENDER_URL")

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

# Функция проверки подписки
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

# Клавиатура со ссылкой на канал и кнопкой проверки
def get_subscribe_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text="Подписаться на канал", url=CHANNEL_URL)],
        [types.InlineKeyboardButton(text="Я подписался!", callback_data="check_subscription")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

# Хэндлер команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if await is_subscribed(user_id):
        await message.answer("Спасибо за подписку! Тебе доступен весь скрытый функционал. Пользуйся! 🎉")
    else:
        await message.answer(
            "Привет! Чтобы получить доступ к боту, пожалуйста, подпишись на наш канал.",
            reply_markup=get_subscribe_keyboard()
        )

# Обработка кнопки "Я подписался!"
@dp.callback_query(lambda c: c.data == "check_subscription")
async def process_check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_subscribed(user_id):
        await callback_query.answer("Подписка подтверждена!", show_alert=True)
        await bot.send_message(
            chat_id=user_id,
            text="Ура! Доступ открыт. Вот твой дополнительный функционал... 🚀"
        )
        await bot.delete_message(chat_id=user_id, message_id=callback_query.message.message_id)
    else:
        await callback_query.answer("Вы всё еще не подписались на канал 😕", show_alert=True)

# Жизненный цикл FastAPI для управления вебхуком
@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте устанавливаем вебхук
    await bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Вебхук установлен на {WEBHOOK_URL}")
    yield
    # При остановке удаляем вебхук
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Сессия бота закрыта, вебхук удален")

# Привязываем lifespan к FastAPI
app = FastAPI(lifespan=lifespan)

# Эндпоинт для приема обновлений от Telegram
@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"status": "ok"}

# Простой эндпоинт для проверки работоспособности сервиса (и пинга)
@app.get("/")
async def index():
    return {"status": "alive"}