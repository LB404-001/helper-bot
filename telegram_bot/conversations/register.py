from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from logging import Logger

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.sessions import Sessions, RedisSessions
from telegram_bot.decorators.require_session import require_session

LOGIN, PASSWORD = range(2)

class Register:

    def __init__(self, sessions: RedisSessions, auth: Authorization, logger: Logger):
        self.logger = logger
        self.auth = auth
        self.sessions = sessions

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.logger.info("Register conversation initialized")

        context.user_data.pop("login", None)
        context.user_data.pop("password", None)

        await update.message.reply_text("Введите логин")
        
        return LOGIN

    async def get_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        login = update.message.text

        context.user_data["login"] = login

        exist = self.auth.check_user_exist(login)
        if exist:
            await update.message.reply_text("Логин занят")
            await update.message.reply_text("Введите логин")
            return LOGIN

        await update.message.reply_text("Введите пароль")
        return PASSWORD

    async def get_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        password = update.message.text

        login = context.user_data.get("login", None)
        
        if password is None or login is None:
            await update.message.reply_text("Логин или пароль пусты")
            self.logger.error(f"Empty login or password: {login}|{password}")
            return ConversationHandler.END
        
        #await update.message.reply_text(f"Получены login:{login} password:{password}")
        
        success = self.auth.register_user(login, password)
        if not success:
            self.logger.info(f"Registration error. login:{login}")
            await update.message.reply_text("Ошибка при регистрации, попробуйте позднее")
            return ConversationHandler.END

        self.logger.info(f"user registered. login:{login}")
        await update.message.reply_text("Вы успешно зарегистрированы")

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_chat.send_message("Отменено")
        return ConversationHandler.END

    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("register", self.start)], 
            states={
                LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_login)],
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_password)],
            }, 
            fallbacks=[CommandHandler("cancel", self.cancel)], 
            allow_reentry=True
        )