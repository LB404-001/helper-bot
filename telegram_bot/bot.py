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
            {"command": "tg_remember", "description": "Запомнить меня в системе"},
            {"command": "tg_forget", "description": "Забыть меня из системы"},
            {"command": "start", "description": "Начать работу с ботом"},
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

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool | None:
        status = context.user_data.get('status')
        logger.info("Login initialized")

        if status == AUTH_STATUS.AUTHORIZATION.value:
            if len(update.message.text.split(' ')) < 2:
                await update.message.reply_text("Введите и логин и пароль!")
                return False
            
            login, password = update.message.text.split(' ')
            id = self.auth.authenticate_user(login, password)
            if id:
                token = self.sessions.new_session(id)
                if token is None:
                    logger.error(f"token for user:{id} is none")
                    return False
                logger.info(f"initialized new session:{token} for user:{id}")
                
                context.user_data['status'] = AUTH_STATUS.AUTHORIZED.value
                context.user_data['token'] = token
                context.user_data['id'] = id
                logger.info(f"User:{id} authenticated")

                await self.remember_user(id, update, True)
                await update.message.reply_text("Вы успешно вошли в систему!")

                return True
            
            else:
                logger.warning(f"User:{id} authentication failed")

                await update.message.reply_text("Неверный логин или пароль.")

                return False
        
        #try auto authorization (by tg)
        await update.message.reply_text("Проверка авторизации...")

        user_id = update.message.from_user.id
        id = self.auth.authenticate_user_by_tg(telegram_id=user_id)

        if id:
            token = self.sessions.new_session(id)
            if token is None:
                logger.error(f"token for user:{id} is none")
                return False
            logger.info(f"initialized new session:{token} for user:{id}")
            
            context.user_data['status'] = AUTH_STATUS.AUTHORIZED.value
            context.user_data['token'] = token
            context.user_data['id'] = id
            logger.info(f"User:{user_id} authenticated")

            await update.message.reply_text("Вы успешно вошли в систему!")

            return True
        
        else:
            logger.warning(f"User:{user_id} tg authentication failed")
            context.user_data['status'] = AUTH_STATUS.AUTHORIZATION.value
            logger.debug(f"current user status:{context.user_data['status']}")

            await update.message.reply_text("Ошибка авторизации. Пожалуйста, введите логин и пароль в формате: 'логин пароль'")
        
        return False

    async def remember_user(self, user_id: int, update: Update, value: bool = True):
        self.auth.remember_user(user_id, update.message.from_user.id, value)
        logger.info(f"User:{user_id} {f'remembered as tg user:{update.message.from_user.id}' if value else 'forgotten'}")
        await update.message.reply_text(f"Аккаунт {'запомнен' if value else 'забыт'}")

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

    #creating image
    async def create_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = context.user_data.get("status")
        if status == IMG_STATUS.PROMPTING.value:
            prompt = update.message.text
            if prompt is None:
                await update.message.reply_text("Пустой промпт! Введите позитивный промпт")
            cmf = Comfy()
            img = await cmf.base_scene(prompt, "")
            #print(img)
            context.user_data['status'] = ""
            await update.message.reply_photo(photo=img)
            return

        context.user_data['status'] = IMG_STATUS.PROMPTING.value
        await update.message.reply_text("Введите позитивный промпт")
        return

    #handlers
    async def command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split(' ')[0][1:]  # Remove the leading '/'

        token = context.user_data.get("token", None)
        user_id = update.message.from_user.id
        logger.debug(f"Command received from user:{user_id}")

        #commands
        #open
        logger.debug(f"Command {command} execution")
        if command in ["login", "start"]:
            context.user_data['status'] = ""
            await self.login(update, context)
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
                
                case "create_image":
                    await self.create_image(update, context)

                case "new_chat":
                    context.user_data['status'] = ""
                    await self.new_chat(update, context)

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
            match status:
                case AUTH_STATUS.AUTHORIZATION.value:
                    await self.login(update, context)

                case IMG_STATUS.PROMPTING.value:
                    await self.create_image(update, context)

                case _:
                    logger.error(f"Unknown status:{status} from user:{id}")
                    context.user_data[status] = ""
                    await update.message.reply_text("Неизвестная ошибка. Примените команду повторно")

            return

        await update.message.reply_text("Неизвестный аккаут, требуется аутентификация. Используйте /login")
        return False

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
        self.app.add_handler(CommandHandler(["tg_remember", "tg_forget", "start", "login", "create_image"], self.command_handler))
        self.app.add_handler(MessageHandler(filters.TEXT, self.message_handler))
        print("Бот запущен!")
        self.app.run_polling()