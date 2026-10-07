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
        
        await update.message.reply_text(f"Получены login:{login} password:{password}")
        
        self.auth.register_user(login, password)

        id = self.auth.authenticate_user(login, password)
        if id: #creating session
            token = self.sessions.new_session(id)
            if token is None:
                self.logger.error(f"token for user:{id} is none")
                return False
            self.logger.info(f"initialized new session:{token} for user:{id}")
            
            context.user_data['token'] = token
            context.user_data['id'] = id
            self.logger.info(f"User:{id} authenticated")

            await update.message.reply_text("Вы успешно вошли в систему!")
        
        else:
            self.logger.warning(f"User:{id} authentication failed")

            await update.message.reply_text("Неверный логин или пароль.")

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