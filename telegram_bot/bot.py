from turtle import update
from unittest import case
import redis.asyncio
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent.core import Core
import psycopg
import json
import enum
import redis

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.chats import Chats
from telegram_bot.sessions import Sessions, RedisSessions
from agent.comfy.comfy import Comfy

from telegram_bot.conversations.image_gen import ImageGen
from telegram_bot.conversations.auth import Login
from telegram_bot.conversations.register import Register
from telegram_bot.conversations.remember_user import Remember

import logging

from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(
    action="ignore",
    message=r".*CallbackQueryHandler",
    category=PTBUserWarning,
)

log_level_colors = {
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.DEBUG: "\033[36m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[41m",
    "RESET": "\033[0m"
}

class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = log_level_colors.get(record.levelno)
        reset = log_level_colors.get("RESET")
        message = super().format(record)
        return f"{color}{message}{reset}"

log_handler = logging.StreamHandler()
log_handler.setFormatter(ColorFormatter("%(asctime)s [%(levelname)s] - %(message)s"))

logger = logging.getLogger("bot")
logger.setLevel(logging.DEBUG)
logger.addHandler(log_handler)


SETTINGS = json.load(open("telegram_bot/local_settings.json", "r"))

TOKEN = SETTINGS["token"]
WEBHOOK_SETTINGS = SETTINGS["webhook_settings"]
DB_CONNECTION_SETTINGS = SETTINGS["db_connection_settings"]
REDIS_CONNECTION_SETTINGS = SETTINGS["redis_connection_settings"]

class AUTH_STATUS(enum.Enum):
    AUTHORIZED = "authorized"
    AUTHORIZATION = "authorization"
    UNAUTHORIZED = "unauthorized"

class CHAT_STATUS(enum.Enum):
    SELECTING = "selecting"
    SELECTED = "selected"
    CREATING = "creating"
    DELETING = "deleting"

class IMG_STATUS(enum.Enum):
    PROMPTING = "prompting"
    PROCESSING = "processing"
    COMPLETE = "complete"

class SCENARIOS(enum.Enum):
    LOGIN = "login"
    CHAT = "chat"
    IMAGE_GEN = "image_gen"

class Bot:
    def __init__(self, token=TOKEN):
        self.token = token
        self.DB: psycopg.Connection
        self.sessions: RedisSessions
        self.auth: Authorization
        self.chats: Chats
        self.app = (Application.builder()
                    .token(self.token)
                    .post_init(self.post_init)
                    .post_shutdown(self.post_shutdown)
                    .build())

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Привет!")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        error = context.error

        logger.error(f"Unhandled error:{error}")
        text = "Произошла ошибка, мы уже разбираемся."

        if isinstance(error, (redis.RedisError, ConnectionError, TimeoutError)):
            text = "Сервис временно недоступен, попробуйте через минуту."
        
        if update and getattr(update, "effective_message", None):
            try:
                await update.effective_message.reply_text(text)
            except Exception:
                pass

    async def post_init(self, app: Application):
        await self.auth.connect(**DB_CONNECTION_SETTINGS)
    
    async def post_shutdown(self, app: Application):
        await self.auth.disconnect()

    def build(self):

        self.sessions = RedisSessions(redis.asyncio.Redis(**REDIS_CONNECTION_SETTINGS), logger)
        self.auth = Authorization(**DB_CONNECTION_SETTINGS, logger=logger)

        img = ImageGen(sessions=self.sessions, token=TOKEN, logger=logger)
        auth = Login(sessions=self.sessions, auth=self.auth, logger=logger)
        register = Register(sessions=self.sessions, auth=self.auth, logger=logger)
        remember = Remember(sessions=self.sessions, auth=self.auth, logger=logger)

        self.app.add_handler(img.handler())
        self.app.add_handler(auth.handler())
        self.app.add_handler(register.handler())
        self.app.add_handler(remember.handler())

        self.app.add_handler(CommandHandler("start", self.start))

        self.app.add_error_handler(self.error_handler)

    def run(self, mode: str):

        self.build()

        response = requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteMyCommands")
        commands = [
            {"command": "remember", "description": "Запомнить меня в системе"},
            {"command": "start", "description": "Начать работу с ботом"},
            {"command": "register", "description": "Зарегистрироваться в системе"},
            {"command": "login", "description": "Войти в систему"},
            {"command": "create_image", "description": "Создать изображение"},
            {"command": "cancel", "description": "Отмена"},
        ]
        response = requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands", json={"commands": commands})

        match mode:
            case "webhook":
                print("Бот запущен!")
                self.app.run_webhook(**WEBHOOK_SETTINGS)
            case "polling":
                print("Бот запущен!")
                self.app.run_polling()
            case _ :
                print("unknown mode")
        