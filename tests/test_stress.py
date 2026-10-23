import asyncio, pytest, random

#from test_registration import test_normal, test_login_normal, test_remember, test_user_exist

@pytest.fixture(scope="module")
def username():
    rnd = random.Random()
    username = f"test_user_reg-{rnd.randint(0, 999999999)}"
    return username

async def standard_scenario(user, username):
    assert await user.say("/register") == ["Введите логин"]
    assert await user.say(username) == ["Введите пароль"]
    assert await user.say(username) == ["Вы успешно зарегистрированы"]

    assert await user.say("/register") == ["Введите логин"]
    assert await user.say(username) == ["Логин занят", "Введите логин"]
    assert await user.say(f"{username}-second") == ["Введите пароль"]
    assert await user.say(f"{username}-second") == ["Вы успешно зарегистрированы"]

    assert await user.say("/login") == ["Проверка авторизации...", "Ошибка авторизации.", "Введите логин"]
    assert await user.say(username) == ["Введите пароль"]
    assert await user.say(username) == ["Вы успешно вошли в систему!"]

    assert await user.say("/remember") == ["Запомнить этот тг аккаунт?"]

@pytest.mark.asyncio
@pytest.mark.parametrize("users_count", [10])
async def test_stress(bot, fake, user, users_count):
    users = []

    for i in range(users_count):
        u = type(user)(bot, fake)
        users.append(u)
    
    await asyncio.gather(
        *(standard_scenario(u, f"stress-user-{u.user_id}") for u in users)
    )