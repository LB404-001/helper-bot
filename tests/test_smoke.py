async def test_start(user):
    replies = await user.say("/start")
    print(replies)          # запуск: pytest -s
    assert replies