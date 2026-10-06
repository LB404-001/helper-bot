
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from agent.comfy.comfy import Comfy

MODEL, POSITIVE, NEGATIVE, CONFIRM = range(4)

class ImageGen:

    def __init__(self):
        self.models = {
            "2": "novaAnimeXL_ilV180.safetensors",
            "1": "AnythingXL_xl.safetensors"
        }

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[
            InlineKeyboardButton("Общая", callback_data="1"),
            InlineKeyboardButton("Аниме персонажи", callback_data="2")
        ]]
        await update.message.reply_text(f"Выберите модель", reply_markup=InlineKeyboardMarkup(keyboard))

        context.user_data.pop("positive_prompt", None)
        context.user_data.pop("negative_prompt", None)
        context.user_data.pop("model", None)

        return MODEL
    
    async def get_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        context.user_data["model"] = self.models.get(query.data, None)

        if context.user_data["model"] is None:
            await query.message.chat.send_message("Неизвестная модель")
            return ConversationHandler.END
        await query.message.chat.send_message("Введите позитивный промпт")
        return POSITIVE

    async def get_positive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["positive_prompt"] = update.message.text

        await update.message.reply_text("Введите негативный промпт")
        return NEGATIVE

    async def get_negative(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["negative_prompt"] = update.message.text

        positive = context.user_data.get("positive_prompt", None)
        negative = context.user_data.get("negative_prompt", None)
        model = context.user_data.get("model", None)

        await update.message.reply_text(f"Получены промпты:\nPositive:{positive}\nNegative:{negative}\nModel:{model}")

        keyboard = [[
            InlineKeyboardButton("Да", callback_data="True"),
            InlineKeyboardButton("Нет", callback_data="False")
        ]]

        await update.message.reply_text("Сгенерировать?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CONFIRM

    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        positive = context.user_data.get("positive_prompt", None)
        negative = context.user_data.get("negative_prompt", None)
        model = context.user_data.get("model", None)

        if positive is None or negative is None or model is None:
            await query.message.chat.send_message("Часть данных пусты")
            return ConversationHandler.END

        if query.data == "True":
            cmf = Comfy()
            msg = await query.message.chat.send_message("Отравка запроса...")

            img = await cmf.base_scene(positive, negative, model, msg.edit_text)

            if isinstance(img, bytes):
                await query.message.chat.send_photo(photo=img)
                return ConversationHandler.END

            await query.message.chat.send_message(img)
        await query.message.chat.send_message("Неизвестная ошибка")
        return ConversationHandler.END
    
    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("create_image", self.start)], 
            states={
                MODEL: [CallbackQueryHandler(self.get_model)],
                POSITIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_positive)],
                NEGATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_negative)],
                CONFIRM: [CallbackQueryHandler(self.confirm)],
            }, 
            fallbacks=[CommandHandler("confirm", self.confirm)]
        )
