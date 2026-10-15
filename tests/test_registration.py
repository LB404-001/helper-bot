import random, asyncio

import pytest

@pytest.fixture(scope="module")
def username():
    rnd = random.Random()
    username = f"test_user_reg-{rnd.randint(0, 999999999)}"
    return username

@pytest.mark.dependency()
async def test_normal(user, username):
    assert await user.say("/register") == ["Введите логин"]
    assert await user.say(username) == ["Введите пароль"]
    assert await user.say(username) == ["Вы успешно зарегистрированы"]

@pytest.mark.dependency(depends=["test_normal"])
async def test_user_exist(user, username):
    assert await user.say("/register") == ["Введите логин"]
    assert await user.say(username) == ["Логин занят", "Введите логин"]
    assert await user.say(f"{username}-second") == ["Введите пароль"]
    assert await user.say(f"{username}-second") == ["Вы успешно зарегистрированы"]

@pytest.mark.dependency(depends=["test_normal"])
async def test_login_normal(user, username):
    assert await user.say("/login") == ["Проверка авторизации...", "Ошибка авторизации.", "Введите логин"]
    assert await user.say(username) == ["Введите пароль"]
    assert await user.say(username) == ["Вы успешно вошли в систему!"]
    return user, username

@pytest.mark.dependency(depends=["test_login_normal"])
async def test_remember(user, username):
    user, username = await test_login_normal(user, username)
    assert await user.say("/remember") == ["Запомнить этот тг аккаунт?"]