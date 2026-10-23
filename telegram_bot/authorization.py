from click import command
import psycopg, asyncpg
import enum
from argon2 import PasswordHasher
from logging import Logger

class Identifiers(enum.Enum):
    ID = "id"
    TELEGRAM_ID = "telegram_id"

class Authorization:
    def __init__(self, host, port, dbname, user, password, logger: Logger):
        self.ph = PasswordHasher()
        self.logger = logger
    
    async def connect(self, host, port, dbname, user, password):
        self.pool = await asyncpg.create_pool(
            host=host, 
            port=port, 
            password=password, 
            user=user, 
            database=dbname, 
            command_timeout=60, 
            min_size=10, 
            max_size=20
            )
    
    async def disconnect(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def authenticate_user(self, login: str = None, password: str = None) -> int | bool:
        #auth by login
        if (login is None) or (password is None):
            return False
        
        async with self.pool.acquire() as conn:
                #cursor.execute("SELECT id FROM users WHERE login = %s AND password = %s", (login, password))
                res = await conn.fetchrow("SELECT id, password FROM users WHERE login = $1", (login))
                if res is None:
                    return False
                id, pwd = res

                au = False
                try:
                    au = self.ph.verify(pwd, password)
                except:
                    return False
                
                if au: 
                    return id
        
        return False

    async def check_user_exist(self, login: str) -> bool:

        async with self.pool.acquire() as conn:
            #cursor.execute("SELECT id FROM users WHERE login = %s AND password = %s", (login, password))
            res = await conn.fetchrow("SELECT id FROM users WHERE login = $1", (login))
            if res is not None:
                return True

        return False

    async def register_user(self, login: str = None, password: str = None) -> bool:
        #auth by login
        if (login is None) or (password is None):
            self.logger.error(f"{login}-{password}")
            return False

        async with self.pool.acquire() as conn:
            #cursor.execute("SELECT id FROM users WHERE login = %s AND password = %s", (login, password))
            res = await conn.fetchrow("SELECT id FROM users WHERE login = $1", (login))
            if res is None:
                passwd = self.ph.hash(password)
                st = await conn.execute("INSERT INTO users (login, password) VALUES ($1, $2)", login, passwd)
                return st == "INSERT 0 1"

        return False

    async def authenticate_user_by_tg(self, telegram_id: int) -> int | bool:
        async with self.pool.acquire() as conn:
            res = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", telegram_id)
            return res[0] if res is not None else False
        
        return False

    async def get_authorization(self, identifier: Identifiers, value: int) -> bool:
        if identifier == Identifiers.ID:
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow("SELECT auth_status FROM users WHERE id = $1", value)
                if result:
                    return result[0]
        if identifier == Identifiers.TELEGRAM_ID:
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow("SELECT auth_status FROM users WHERE telegram_id = $1", value)
                if result:
                    return result[0]
        return False

    async def set_authorization(self, identifier: Identifiers, value: int, auth_status: bool = False) -> bool:
        async with self.pool.acquire() as conn:
            status = False
            if identifier == Identifiers.ID:
                st = await conn.execute("UPDATE users SET auth_status = $1 WHERE id = $2", auth_status, value)
                status = st == "INSERT 0 1"
            if identifier == Identifiers.TELEGRAM_ID:
                st = await conn.execute("UPDATE users SET auth_status = $1 WHERE telegram_id = $2", auth_status, value)
                status = st == "INSERT 0 1"
        return status

    async def remember_user(self, id: int, telegram_id: int, status: bool = False) -> bool:
        async with self.pool.acquire() as conn:
            st = await conn.execute("UPDATE users SET telegram_id = $1 WHERE id = $2", (telegram_id if status else None), id)
            status = st == "UPDATE 1"
        
        return status
