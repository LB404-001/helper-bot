from turtle import update
from unittest import case
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent.core import Core
import psycopg
import json
import enum

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.chats import Chats

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
log_handler.setFormatter(ColorFormatter("%(asctime)s [{%(levelname)s}] - %(message)s"))

logger = logging.getLogger("bot")
logger.setLevel(logging.DEBUG)
logger.addHandler(log_handler)


SETTINGS = json.load(open("telegram_bot/settings.json", "r"))

TOKEN = SETTINGS["token"]
DB_SETTINGS = SETTINGS["connection_settings"]

class AUTH_STATUS(enum.Enum):
    AUTHORIZED = "authorized"
    AUTHORIZATION = "authorization"
    UNAUTHORIZED = "unauthorized"

class CHAT_STATUS(enum.Enum):
    SELECTING = "selecting"
    SELECTED = "selected"
    CREATING = "creating"
    DELETING = "deleting"

class SCENARIOS(enum.Enum):
    LOGIN = "login"
    CHAT = "chat"

class Bot:
    def __init__(self, core: Core, token=TOKEN):
        self.core = core
        self.token = token
        self.app = Application.builder().token(self.token).build()
        self.DB = self.db_connect()
        self.auth = Authorization(self.DB)
        self.chats = Chats(self.DB)

        commands = [
            {"command": "tg_remember", "description": "Запомнить меня в системе"},
            {"command": "tg_forget", "description": "Забыть меня из системы"},
            {"command": "start", "description": "Начать работу с ботом"},
            {"command": "login", "description": "Войти в систему"},
            {"command": "new_chat", "description": "Начать новый чат"},
        ]
        response = requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands", json={"commands": commands})

    def db_connect(self):
        return psycopg.connect(**DB_SETTINGS)

    def db_disconnect(self, connection: psycopg.Connection = None):
        if connection:
            connection.close()
        else:
            self.DB.close()

    #user management

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool | None:
        status = context.user_data.get('status')
        logger.info("Login initialized")

        if status == AUTH_STATUS.AUTHORIZATION.value:
            login, password = update.message.text.split(' ')
            auth_status = self.auth.authenticate_user(login, password)
            if auth_status:
                self.remember_user()
                context.user_data['status'] = AUTH_STATUS.AUTHORIZED.value
                logger.info(f"User:{login} authenticated")
                await update.message.reply_text("Вы успешно вошли в систему!")
                return True
            else:
                logger.warning(f"User:{login} authentication failed")
                await update.message.reply_text("Неверный логин или пароль.")
                return False
        
        #try auto authorization (by tg)
        await update.message.reply_text("Проверка авторизации...")
        user_id = update.message.from_user.id
        auth_status = self.auth.authenticate_user(telegram_id=user_id)

        if auth_status:
            self.remember_user()
            context.user_data['status'] = AUTH_STATUS.AUTHORIZED.value
            logger.info(f"User:{login} authenticated")
            await update.message.reply_text("Вы успешно вошли в систему!")
            return True
        
        else:
            logger.warning(f"User:{login} authentication failed")
            context.user_data['status'] = AUTH_STATUS.AUTHORIZATION.value
            logger.debug(f"current user status:{context.user_data['status']}")
            await update.message.reply_text("Ошибка авторизации. Пожалуйста, введите логин и пароль в формате: 'логин пароль'")
        
        return False

    async def remember_user(self, update: Update, value: bool = True):
        self.auth.remember_user(update.message.from_user.id, update.message.from_user.id, status=value)
        logger.info(f"User:{update.message.from_user.id} remembered")
        await update.message.reply_text(f"remember telegram:{value}")

    #chat management
    async def new_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = context.user_data.get('status')
        user_id = update.message.from_user.id

        if not self.auth.get_authorization(Identifiers.TELEGRAM_ID, user_id):
            logger.warning(f"Chat creation failed. TG User:{user_id} is not authenticated")
            await update.message.reply_text("Вы должны быть авторизованы, чтобы создать новый чат.")
            return False

        if status == CHAT_STATUS.CREATING.value:
            status = ""
            title = update.message.text
            res = self.chats.add_chat(title)
            if res:
                logger.info(f"Chat:{title} created by tg user:{user_id}")
                update.message.reply_text("Чат создан")
                return True
            logger.error(f"Can't create Chat:{title} by tg user:{user_id}")
            update.message.reply_text("Ошибка при создании чата")
            return False

        status = CHAT_STATUS.CREATING.value
        logger.debug(f"Chat creation initialized by tg user:{user_id}")
        await update.message.reply_text("Введите название нового чата:")
        return 

    #handlers
    async def command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split(' ')[0][1:]  # Remove the leading '/'

        #session check
        #This shit is trying to check user session to identify user
        #Now it is using telegram_id as session token
        user_id = update.message.from_user.id
        logger.debug(f"Command received from user:{user_id}")
        auth_status = self.auth.authenticate_user(telegram_id=user_id)
        if not auth_status:
            update.message.reply_text("Неизвестный аккаут, требуется аутентификация. Используйте /login")

        #commands
        logger.debug(f"Command {command} execution")
        match command:
            case "tg_remember":
                await self.remember_user(update, value=True)

            case "tg_forget":
                await self.remember_user(update, value=False)

            case "start":
                print(context.user_data.get('status'))
                context.user_data['status'] = ""
                await self.login(update, context)

            case "login":
                print(context.user_data.get('status'))
                context.user_data['status'] = ""
                await self.login(update, context)

            case "new_chat":
                context.user_data['status'] = ""
                await self.new_chat(update, context)

            case _:
                await update.message.reply_text(f"Неизвестная команда: {command}")

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            response = "resp"#self.core.process_message(update.message.text)
            await update.message.reply_text(response)

    async def main_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get('status') == AUTH_STATUS.AUTHORIZED.value:
            await self.message_handler(update, context)
        else:
            await self.login(update, context)

    def add_handler(self, handler):
        self.app.add_handler(handler)

        #commands
        async def tg_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await self.remember_user(update, value=True)
        
        async def tg_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await self.remember_user(update, value=False)
        
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            context.user_data['status'] = ""
            await self.login(update, context)
        
        async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
            context.user_data['status'] = ""
            await self.login(update, context)
        
        async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("Неизвестная команда. Пожалуйста, используйте /start для начала работы с ботом.")

    def run(self):
        #self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.main_handler))
        self.app.add_handler(CommandHandler(["tg_remember", "tg_forget", "start", "login"], self.command_handler))
        self.app.add_handler(MessageHandler(filters.TEXT, self.main_handler))
        print("Бот запущен!")
        self.app.run_polling()