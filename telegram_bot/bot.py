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

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool | None:
        status = context.user_data.get('status')

        if status == AUTH_STATUS.AUTHORIZATION.value:
            login, password = update.message.text.split(' ')
            auth_status = self.auth.authenticate_user(login, password)
            if auth_status:
                context.user_data['status'] = AUTH_STATUS.AUTHORIZED.value
                await update.message.reply_text("Вы успешно вошли в систему!")
                return True
            else:
                await update.message.reply_text("Неверный логин или пароль.")
                return False

        if status == AUTH_STATUS.AUTHORIZED.value:
            await update.message.reply_text("Вы уже авторизованы.")
            return True
        
        #try auto authorization (by tg)
        await update.message.reply_text("Проверка авторизации...")
        user_id = update.message.from_user.id
        auth_status = self.auth.get_authorization(Identifiers.TELEGRAM_ID, user_id)

        if auth_status:
            context.user_data['status'] = AUTH_STATUS.AUTHORIZED.value
            await update.message.reply_text("Вы успешно вошли в систему!")
            return True
        
        else:
            context.user_data['status'] = AUTH_STATUS.AUTHORIZATION.value
            await update.message.reply_text("Ошибка авторизации. Пожалуйста, введите логин и пароль в формате: 'логин пароль'")
        
        return False

    async def remember_user(self, update: Update, value: bool = True):
        if value:
            self.auth.remember_user(update.message.from_user.id, update.message.from_user.id, status=True)
        else:
            self.auth.remember_user(update.message.from_user.id, update.message.from_user.id, status=False)
        await update.message.reply_text(f"remember telegram:{value}")

    async def command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split(' ')[0][1:]  # Remove the leading '/'
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