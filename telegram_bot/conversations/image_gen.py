
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from agent.comfy.comfy import Comfy
from agent.comfy.worker import generate_image

from telegram_bot.decorators.require_session import require_session

from logging import Logger

MODEL, POSITIVE, NEGATIVE, CONFIRM = range(4)

class ImageGen:

    def __init__(self, sessions, token: str, logger: Logger):
        self.models = {
            "аниме персонажи": "novaAnimeXL_ilV180.safetensors",
            "общая": "AnythingXL_xl.safetensors"
        }
        self.logger = logger
        self.sessions = sessions
        self.token = token

    @require_session
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[k for k, v in self.models.items()]]
        await update.message.reply_text(f"Выберите модель", reply_markup=ReplyKeyboardMarkup(keyboard))

        context.user_data.pop("positive_prompt", None)
        context.user_data.pop("negative_prompt", None)
        context.user_data.pop("model", None)

        return MODEL
    
    @require_session
    async def get_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["model"] = self.models.get(update.message.text.lower(), None)

        if context.user_data["model"] is None:
            await update.message.reply_text("Неизвестная модель", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await update.message.reply_text("Введите позитивный промпт", reply_markup=ReplyKeyboardRemove())
        return POSITIVE

    @require_session
    async def get_positive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["positive_prompt"] = update.message.text

        await update.message.reply_text("Введите негативный промпт")
        return NEGATIVE

    @require_session
    async def get_negative(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["negative_prompt"] = update.message.text

        positive = context.user_data.get("positive_prompt", None)
        negative = context.user_data.get("negative_prompt", None)
        model = context.user_data.get("model", None)

        await update.message.reply_text(f"Получены промпты:\nPositive:{positive}\nNegative:{negative}\nModel:{model}")

        keyboard = [[
            KeyboardButton("Да"),
            KeyboardButton("Нет")
        ]]

        await update.message.reply_text("Сгенерировать?", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        return CONFIRM

    @require_session
    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        positive = context.user_data.get("positive_prompt", None)
        negative = context.user_data.get("negative_prompt", None)
        model = context.user_data.get("model", None)

        if positive is None or negative is None or model is None:
            await update.message.reply_text("Часть данных пусты", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        if update.message.text.lower() == "да":
            await update.effective_chat.send_message("Прогресс", reply_markup=ReplyKeyboardRemove())
            msg = await update.effective_chat.send_message("В очереди")

            task = generate_image.delay(
                self.token,
                update.effective_chat.id,
                msg.message_id,
                positive,
                negative,
                model
            )
            return ConversationHandler.END

        elif update.message.text.lower() == "нет":
            return await self.cancel(update, context)

        await update.message.reply_text("Неизвестная ошибка")
        return await self.cancel(update, context)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_chat.send_message("Отменено", reply_markup=ReplyKeyboardRemove())
        context.user_data.pop("positive_prompt", None)
        context.user_data.pop("negative_prompt", None)
        context.user_data.pop("model", None)
        return ConversationHandler.END
    
    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("create_image", self.start)], 
            states={
                MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_model)],
                POSITIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_positive)],
                NEGATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_negative)],
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm)],
            }, 
            fallbacks=[CommandHandler("cancel", self.cancel)], 
            allow_reentry=True
        )
