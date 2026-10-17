from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
            KeyboardButton("Да"),
            KeyboardButton("Нет")
        ]]

        await update.message.reply_text("Запомнить этот тг аккаунт?", reply_markup=ReplyKeyboardMarkup(keyboard))
        
        return CONFIRM

    @require_session
    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        token = context.user_data.get("token", None)
        uid = context.user_data.get("id", None)

        st = False

        match update.message.text:
            case "Да":
                await self.auth.remember_user(uid, user_id, True)
            case "Нет":
                await self.auth.remember_user(uid, user_id, False)
            case _:
                await update.message.reply_text("Неизвестный параметр", reply_markup=ReplyKeyboardRemove())
                return ConversationHandler.END

        await update.message.reply_text(
            f"Ваш аккаунт:{user_id} {"запомнен" if update.message.text == "Да" else "забыт"}",
            reply_markup=ReplyKeyboardRemove()
            )

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_chat.send_message("Отменено")
        return ConversationHandler.END

    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("remember", self.start)], 
            states={
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm)],
            }, 
            fallbacks=[CommandHandler("cancel", self.cancel)], 
            allow_reentry=True
        )