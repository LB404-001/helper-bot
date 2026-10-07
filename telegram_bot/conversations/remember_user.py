from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from logging import Logger

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.sessions import Sessions, RedisSessions

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

    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
    
    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("register", self.start)], 
            states={
                LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_login)],
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_password)],
            }, 
            fallbacks=[CommandHandler("auth", self.get_password)]
        )