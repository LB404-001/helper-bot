import random

async def test_start(user):
    replies = await user.say("/start")
    print(replies)          # запуск: pytest -s
    assert replies

async def test_register(user):
    rnd = random.Random()
    username = f"test_user_reg-{rnd.randint(0, 999999999)}"
    assert await user.say("/register") == ["Введите логин"]
    assert await user.say(username) == ["Введите пароль"]
    assert await user.say(username) == ["Вы успешно зарегистрированы"]
