from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

from logging import Logger
from functools import wraps

def require_session(func):
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        token = context.user_data.get("token", None)
        id = context.user_data.get("id", None)

        self.logger.debug(f"Session checking for token:{token} and user: {id} from tg user:{user_id}")
        session_status = self.sessions.check_session(id, token)
        self.logger.debug(f"Session status:{session_status} for tg user:{user_id}")

        if session_status:
            return await func(self, update, context)
        await update.effective_chat.send_message("Ошибка, неизвестный аккаунт\nВозможно ваша сессия истекла, авторизуйтесь повторно")
        return ConversationHandler.END
    return wrapper