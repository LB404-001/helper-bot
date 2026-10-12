async def test_start(user):
    replies = await user.say("/start")
    print(replies)          # запуск: pytest -s
    assert replies

async def test_register(user):
    print(await user.say("/register"))
    print(await user.say("user123"))
    print(await user.say("user123"))
