from turtle import update
from unittest import case
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
    def __init__(self, core: Core, token=TOKEN):
        self.core = core
        self.token = token
        self.app = Application.builder().token(self.token).build()
        self.DB = psycopg.connect(**DB_CONNECTION_SETTINGS)
        self.sessions = RedisSessions(redis.Redis(**REDIS_CONNECTION_SETTINGS))#Sessions(self.DB)
        self.auth = Authorization(self.DB)
        self.chats = Chats(self.DB)

        commands = [
            {"command": "remember", "description": "Запомнить меня в системе"},
            {"command": "start", "description": "Начать работу с ботом"},
            {"command": "register", "description": "Зарегистрироваться в системе"},
            {"command": "login", "description": "Войти в систему"},
            {"command": "new_chat", "description": "Начать новый чат"},
            {"command": "create_image", "description": "Создать изображение"},
        ]
        response = requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands", json={"commands": commands})

    def db_connect(self):
        return psycopg.connect(**DB_CONNECTION_SETTINGS)

    def db_disconnect(self, connection: psycopg.Connection = None):
        if connection:
            connection.close()
        else:
            self.DB.close()

    #user management

    async def remember_user(self, user_id: int, update: Update, value: bool = True):
        self.auth.remember_user(user_id, update.message.from_user.id, value)
        logger.info(f"User:{user_id} {f'remembered as tg user:{update.message.from_user.id}' if value else 'forgotten'}")
        await update.message.reply_text(f"Аккаунт {'запомнен' if value else 'забыт'}")

    #handlers
    async def command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split(' ')[0][1:]  # Remove the leading '/'

        token = context.user_data.get("token", None)
        context.user_data["scenario"] = None
        user_id = update.message.from_user.id
        logger.debug(f"Command received from user:{user_id}")

        #commands
        #open
        logger.debug(f"Command {command} execution")
        if command in ["login", "start"]:
            context.user_data['status'] = None
            context.user_data["scenario"] = SCENARIOS.LOGIN.value
            return False

        #protected
        id = context.user_data.get("id", None)
        logger.debug(f"Session checking for token:{token} and user: {id} from tg user:{user_id}")
        session_status = self.sessions.check_session(id, token)
        logger.debug(f"Session status:{session_status} for tg user:{user_id}")
        if session_status:
            match command:
                case "tg_remember":
                    await self.remember_user(id, update, value=True)

                case "tg_forget":
                    await self.remember_user(id, update, value=False)
                
                # case "create_image":
                #     context.user_data["scenario"] = SCENARIOS.IMAGE_GEN.value
                #     context.user_data["status"] = None
                #     await self.create_image(update, context)

                case _:
                    await update.message.reply_text(f"Неизвестная команда: {command}")
            return

        await update.message.reply_text("Неизвестный аккаут, требуется аутентификация. Используйте /login")
        return False


    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            response = "resp"#self.core.process_message(update.message.text)
            await update.message.reply_text(response)

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        token = context.user_data.get("token", None)
        user_id = update.message.from_user.id
        logger.debug(f"Message received from user:{user_id}")

        message = update.message.text

        #commands
        #open
        logger.debug(f"Message {message} execution")

        #protected
        id = context.user_data.get("id", None)
        logger.debug(f"Session checking for token:{token} and user: {id} from tg user:{user_id}")
        session_status = self.sessions.check_session(id, token)
        logger.debug(f"Session status:{session_status} for tg user:{user_id}")

        if session_status:
            status = context.user_data.get("status")
            scenario = context.user_data.get("scenario")
            match scenario:
                case _:
                    logger.error(f"Unknown scenario:{status} from user:{id}")
                    context.user_data["status"] = ""
                    context.user_data["scenario"] = None
                    await update.message.reply_text("Неизвестная ошибка. Примените команду повторно")

            return

        await update.message.reply_text("Неизвестный аккаут, требуется аутентификация. Используйте /login")
        return False


    def run(self):

        img = ImageGen()
        auth = Login(sessions=self.sessions, auth=self.auth, logger=logger)
        register = Register(sessions=self.sessions, auth=self.auth, logger=logger)
        remember = Remember(sessions=self.sessions, auth=self.auth, logger=logger)

        self.app.add_handler(img.handler())
        self.app.add_handler(auth.handler())
        self.app.add_handler(register.handler())
        self.app.add_handler(remember.handler())

        #self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.main_handler))
        #self.app.add_handler(CommandHandler(["tg_remember", "tg_forget", "start", "login", "create_image"], self.command_handler))
        #self.app.add_handler(MessageHandler(filters.TEXT, self.message_handler))

        print("Бот запущен!")
        self.app.run_polling()