from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

from logging import Logger

from telegram_bot.authorization import Authorization, Identifiers
from telegram_bot.sessions import Sessions, RedisSessions
from telegram_bot.decorators.require_session import require_session

CONFIRM = range(1)

class Remember:

    def __init__(self, sessions: RedisSessions, auth: Authorization, logger: Logger):
        self.logger = logger
        self.auth = auth
        self.sessions = sessions

    @require_session
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.logger.info("Remember conversation initialized")

        keyboard = [[
            InlineKeyboardButton("Да", callback_data="confirm:y"),
            InlineKeyboardButton("Нет", callback_data="confirm:n")
        ]]

        await update.message.reply_text("Запомнить этот тг аккаунт?", reply_markup=InlineKeyboardMarkup(keyboard))
        
        return CONFIRM

    @require_session
    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        token = context.user_data.get("token", None)
        uid = context.user_data.get("id", None)
        if query.data == "confirm:y":
            self.auth.remember_user(uid, user_id, True)
        else:
            self.auth.remember_user(uid, user_id, False)

        await query.message.chat.send_message(f"Ваш аккаунт:{user_id} {"запомнен" if query.data == "confirm:y" else "забыт"}")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_chat.send_message("Отменено")
        return ConversationHandler.END

    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("remember", self.start)], 
            states={
                CONFIRM: [CallbackQueryHandler(self.confirm, pattern=r"^confirm:")],
            }, 
            fallbacks=[CommandHandler("cancel", self.cancel)], 
            allow_reentry=True
        )