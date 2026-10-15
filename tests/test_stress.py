import asyncio, pytest, random

from test_registration import test_normal, test_login_normal, test_remember, test_user_exist

@pytest.fixture(scope="module")
def username():
    rnd = random.Random()
    username = f"test_user_reg-{rnd.randint(0, 999999999)}"
    return username

async def standard_scenario(user, username):
    await test_normal(user, username)
    await test_user_exist(user, username)
    await test_login_normal(user, username)
    await test_remember(user, username)

@pytest.mark.asyncio
@pytest.mark.parametrize("users_count", [10, 50, 100])
async def test_stress(bot, fake, user, users_count):
    users = []

    for i in range(users_count):
        u = type(user)(bot, fake)
        users.append(u)
    
    await asyncio.gather(
        *(standard_scenario(u, f"stress-user-{u.user_id}") for u in users)
    )