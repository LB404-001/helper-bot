from agent.llm import LLM
from telegram_bot.bot import Bot
from agent.core import Core


llm = LLM(model_name="qwen3:8b")
core = Core(llm=llm)
bot = Bot(core=core)

bot.run()