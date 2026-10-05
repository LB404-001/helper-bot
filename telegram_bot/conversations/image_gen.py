
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from agent.comfy.comfy import Comfy

POSITIVE, NEGATIVE, CONFIRM, END = range(4)

class ImageGen:

    def __init__(self):
        self.prompt_positive = ""
        self.prompt_negative = ""

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Введите позитивный промпт")
        return POSITIVE

    async def get_positive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.prompt_positive = update.message.text
        await update.message.reply_text("Введите негативный промпт")
        return NEGATIVE

    async def get_negative(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.prompt_negative = update.message.text
        await update.message.reply_text(f"Получены промпты:\nPositive:{self.prompt_positive}\nNegative:{self.prompt_negative}")
        await update.message.reply_text("Сгенерировать? да/нет")
        return CONFIRM

    async def confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.message.text
        if msg == "да":
            cmf = Comfy()
            msg = await update.message.reply_text("Отравка запроса...")
            img = await cmf.base_scene(self.prompt_positive, self.prompt_negative, msg.edit_text)

            if isinstance(img, bytes):
                await update.message.reply_photo(photo=img)
                return ConversationHandler.END

            await update.message.reply_text(img)
        await update.message.reply_text("Отменено")
        return ConversationHandler.END
    
    def handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("create_image", self.start)], 
            states={
                POSITIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_positive)],
                NEGATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_negative)],
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm)],
            }, 
            fallbacks=[CommandHandler("confirm", self.confirm)]
        )
