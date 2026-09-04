from turtle import update

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from agent.core import Core
import psycopg
import json
import enum

SETTINGS = json.load(open("telegram_bot/settings.json", "r"))

TOKEN = SETTINGS["token"]
DB_SETTINGS = SETTINGS["connection_settings"]

class STATUS(enum.Enum):
    LOGGED_IN = "logged_in"
    AUTHORIZATION = "authorization"
    LOGGED_OUT = "logged_out"

class Bot:
    def __init__(self, core: Core, token=TOKEN):
        self.core = core
        self.token = token
        self.app = Application.builder().token(self.token).build()
        self.DB = self.db_connect()
    
    def db_connect(self):
        return psycopg.connect(**DB_SETTINGS)
    
    def db_disconnect(self, connection: psycopg.Connection = None):
        if connection:
            connection.close()
        else:
            self.DB.close()

    def db_auth(self, user_id: int) -> bool:
        with self.DB.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
            user = cursor.fetchone()
        return user is not None

    def db_auth(self, name: str, password: str, status: bool) -> bool:
        with self.DB.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE name = %s AND password = %s", (name, password))
            user = cursor.fetchone()

            if user:
                print(f"Пользователь {name} авторизован.")
                cursor.execute("UPDATE users SET auth_status = %s WHERE name = %s AND password = %s", (status, name, password))
                return True

            print(f"Пользователь {name} не найден или неверный пароль.")
            return False

    async def logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool | None:
        context.user_data['status'] = STATUS.LOGGED_OUT.value
        await update.message.reply_text("You have been logged out.")
        return True

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool | None:
        if context.user_data.get('status') not in [STATUS.LOGGED_OUT.value, STATUS.AUTHORIZATION.value]:
            await update.message.reply_text("Unexpected state. Log out.")
            await self.logout(update, context)
        
        if (context.user_data.get('status') == STATUS.LOGGED_OUT.value):
            await update.message.reply_text("Please enter your username and password separated by a space.")
            context.user_data['status'] = STATUS.AUTHORIZATION.value
            return None

        if (context.user_data.get('status') == STATUS.AUTHORIZATION.value):
            credentials = update.message.text.split()

            if len(credentials) != 2:
                await update.message.reply_text("Please provide both username and password.")
                return None

            name, password = credentials

            if self.db_login(name, password):
                context.user_data['status'] = STATUS.LOGGED_IN.value
                await update.message.reply_text("Login successful!")
                return True

            await update.message.reply_text("Login failed. Please try again.")
            return False
        await update.message.reply_text("Unexpected error. Please try again.")
        return None

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            response = self.core.process_message(update.message.text)
            await update.message.reply_text(response)

    async def main_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get('status') == STATUS.LOGGED_IN.value:
            await self.message_handler(update, context)
        await self.login(update, context)

    def add_handler(self, handler):
        self.app.add_handler(handler)

    def run(self):
        #self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.main_handler))
        self.app.add_handler(MessageHandler(filters.TEXT, self.main_handler))
        #self.app.add_handler(MessageHandler(filters.COMMAND, self.login))
        print("Бот запущен!")
        self.app.run_polling()