import psycopg
import enum
import hashlib
import secrets
from logging import Logger

class Sessions:
    def __init__(self, db_connection: psycopg.Connection, logger: Logger):
        self.db_connection = db_connection
        self.logger = logger
    
    #create new session
    def new_session(self, user_id:int) -> str | None:
        #set user id as session token
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM sessions WHERE user_id = %s", (user_id,))

            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO sessions VALUES (%s)", (user_id,))

            cursor.execute("UPDATE sessions SET token = %s WHERE user_id = %s", (user_id, user_id))
            if cursor.rowcount > 0:
                self.db_connection.commit()
                return str(user_id)
            else:
                self.db_connection.rollback()
        return None
    
    def check_session(self, id: int, token: str) -> bool:
        if id is None or token is None:
            return False
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT token FROM sessions WHERE user_id = %s", (id,))
            res = cursor.fetchone()
            return res[0] == token
        return False

import redis
class RedisSessions:
    def __init__(self, redis_connection: redis.Redis, logger: Logger):
        self.redis: redis.Redis = redis_connection
        self.logger = logger

    def new_session(self, id:int) -> str | None:
        #id-token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.redis.set(f"session:{id}", token_hash, ex=3600)
        return token

    def check_session(self, id: int, token:str) -> bool:
        #get token by id
        if id is None or token is None:
            return False
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        tk = self.redis.get(f"session:{id}")

        #expire session
        if tk == token_hash:
            self.redis.expire(f"session:{id}", 3600)
            return True

        return False