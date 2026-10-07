from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

from logging import Logger

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.sessions import Sessions, RedisSessions

CONFIRM = range(1)

class Remember:

    def __init__(self, sessions: RedisSessions, auth: Authorization, logger: Logger):
        self.logger = logger
        self.auth = auth
        self.sessions = sessions

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.logger.info("Remember conversation initialized")

        keyboard = [[
            InlineKeyboardButton("Да", callback_data="y"),
            InlineKeyboardButton("Нет", callback_data="n")
        ]]

        await update.message.reply_text("Запомнить этот тг аккаунт?", reply_markup=InlineKeyboardMarkup(keyboard))
        
        return CONFIRM

    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        token = context.user_data.get("token", None)
        id = context.user_data.get("id", None)

        self.logger.debug(f"Session checking for token:{token} and user: {id} from tg user:{user_id}")
        session_status = self.sessions.check_session(id, token)
        self.logger.debug(f"Session status:{session_status} for tg user:{user_id}")

        if session_status:
            self.auth.remember_user(id, user_id, query.data == "y")

            await query.message.chat.send_message(f"Ваш аккаунт:{user_id} {"запомнен" if query.data == "y" else "забыт"}")
            return ConversationHandler.END
        
        await query.message.chat.send_message(f"Ошибка, Неизвестный аккаунт")
        return ConversationHandler.END
    
    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("remember", self.start)], 
            states={
                CONFIRM: [CallbackQueryHandler(self.confirm)],
            }, 
            fallbacks=[CommandHandler("auth", self.confirm)]
        )