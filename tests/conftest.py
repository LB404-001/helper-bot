from collections import defaultdict
import json, pytest, pytest_asyncio
from unittest.mock import MagicMock
from telegram import Update
from telegram.ext import Application
from telegram.request import BaseRequest, RequestData

import fakeredis, uuid, random, itertools

from telegram_bot.bot import Bot

MESSAGE_METHODS = {"sendMessage", "editMessageText", "editMessageCaption",
                "sendPhoto", "sendDocument", "sendVideo", "sendAudio"}

class FakeRequest(BaseRequest):
    def __init__(self):
        self.sent = defaultdict(list)   # все вызовы API: {"method": ..., **параметры}
        self._mid = itertools.count(1)

    @property
    def read_timeout(self):
        return 5.0

    async def initialize(self): ...
    
    async def shutdown(self): ...

    async def do_request(self, url: str, method: str, request_data: RequestData = None, **kwargs):
        endpoint = url.rsplit("/", 1)[-1]
        data = dict(request_data.parameters) if request_data else {}
        entry = {"method": endpoint, **data}

        if data.get("chat_id", False):
            chat_id = int(data["chat_id"])
            self.sent[chat_id].append(entry)

        if endpoint == "getMe":
            result = {"id": 1, "is_bot": True, "first_name": "T", "username": "t_bot"}

        elif endpoint in MESSAGE_METHODS:
            mid = data.get("message_id") or next(self._mid)   # у edit свой id, у send новый
            entry["message_id"] = mid                        # теперь press найдёт id сообщения
            result = {"message_id": mid, "date": 0,
                    "chat": {"id": int(data["chat_id"]), "type": "private"},
                    "text": data.get("text", "")}
        else:
            result = True
        return 200, json.dumps({"ok": True, "result": result}).encode()

class UserSim:
    def __init__(self, bot: Bot, fake: FakeRequest):
        self.bot = bot
        self.app, self.fake = bot.app, fake
        self.user_id = random.randint(10**9, 10**10)    # уникальный tg id на тест
        self._ids = itertools.count(1)
        self._last = None                               # последнее сообщение бота
        self.calls = []                                 # все вызовы API за последний шаг

    @property
    def data(self):
        """user_data этого пользователя: то, что хендлеры видят как context.user_data."""
        return self.app.user_data[self.user_id]

    @property
    def _user(self):
        return {"id": self.user_id, "is_bot": False, "first_name": "T"}

    @property
    def _chat(self):
        return {"id": self.user_id, "type": "private"}

    async def _deliver(self, payload):

        m = self.fake.sent[self.user_id]
        before = len(m)

        await self.app.process_update(
            Update.de_json({"update_id": next(self._ids), **payload}, self.app.bot))

        if self.bot.errors:
            raise self.bot.errors.pop(0)                # упавший обработчик = упавший тест

        self.calls = m[before:]

        msgs = [c for c in self.calls if c["method"] in MESSAGE_METHODS]

        if msgs:
            self._last = msgs[-1]

        return [c.get("text") or c.get("caption") for c in msgs]

    async def say(self, text: str):
        msg = {"message_id": next(self._ids), "date": 0, "chat": self._chat,
            "from": self._user, "text": text}

        if text.startswith("/"):
            msg["entities"] = [{"type": "bot_command", "offset": 0,
                                "length": len(text.split()[0])}]

        return await self._deliver({"message": msg})

    async def press(self, label):
        """Нажать inline-кнопку по её тексту под последним сообщением бота."""

        markup = self._last.get("reply_markup") or {}
        buttons = [b for row in markup.get("inline_keyboard", []) for b in row]
        btn = next((b for b in buttons if b["text"] == label), None)

        assert btn, f"кнопки {label!r} нет, есть: {[b['text'] for b in buttons]}"

        return await self._deliver({"callback_query": {
            "id": uuid.uuid4().hex, "from": self._user, "chat_instance": "t",
            "data": btn["callback_data"],
            "message": {"message_id": self._last["message_id"], "date": 0, "chat": self._chat},
        }})

@pytest.fixture(scope="module")
def fake(): return FakeRequest()

@pytest_asyncio.fixture
async def bot(fake):

    bot = Bot()
    bot.app = (Application.builder()
                    .token(bot.token)
                    .post_init(bot.post_init)
                    .request(fake)
                    .post_shutdown(bot.post_shutdown)
                    .build())

    await bot.build()

    bot.errors = []
    async def on_error(update, context):
        bot.errors.append(context.error)
    bot.app.add_error_handler(on_error)

    await bot.app.initialize()
    yield bot
    await bot.app.shutdown()

@pytest.fixture
def user(bot, fake):
    return UserSim(bot, fake)

