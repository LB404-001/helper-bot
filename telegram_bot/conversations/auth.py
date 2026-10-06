from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from logging import Logger

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.sessions import Sessions, RedisSessions

LOGIN, PASSWORD = range(2)

class Login:

    def __init__(self, sessions: RedisSessions, auth: Authorization, logger: Logger):
        self.logger = logger
        self.auth = auth
        self.sessions = sessions
        self.password = None
        self.login = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.logger.info("Login conversation initialized")
        self.password = None
        self.login = None
        await update.message.reply_text("Проверка авторизации...")

        user_id = update.message.from_user.id
        self.logger.info("Truing authenticate user by tg")
        id = self.auth.authenticate_user_by_tg(telegram_id=user_id)

        if id:
            token = self.sessions.new_session(id)
            if token is None:
                self.logger.error(f"token for user:{id} is none")
                return False
            self.logger.info(f"initialized new session:{token} for user:{id}")
            
            context.user_data['token'] = token
            context.user_data['id'] = id
            self.logger.info(f"User:{user_id} authenticated")

            await update.message.reply_text("Вы успешно вошли в систему!")

            return ConversationHandler.END
        
        else:
            self.logger.warning(f"User:{user_id} tg authentication failed")

            await update.message.reply_text("Ошибка авторизации.")
            await update.message.reply_text("Введите логин")
        
        return LOGIN

    async def get_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.login = update.message.text
        await update.message.reply_text("Введите пароль")
        return PASSWORD

    async def get_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.password = update.message.text
        
        if self.password is None or self.login is None:
            await update.message.reply_text("Логин или пароль пусты")
            self.logger.error(f"Empty login or password: {self.login}|{self.password}")
            return ConversationHandler.END
        
        await update.message.reply_text(f"Получены login:{self.login} password:{self.password}")
        #authentication
        id = self.auth.authenticate_user(self.login, self.password)
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
    
    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("login", self.start)], 
            states={
                LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_login)],
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_password)],
            }, 
            fallbacks=[CommandHandler("auth", self.password)]
        )