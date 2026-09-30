import psycopg
import enum
from argon2 import PasswordHasher

class Identifiers(enum.Enum):
    ID = "id"
    TELEGRAM_ID = "telegram_id"

class Authorization:
    def __init__(self, db_connection: psycopg.Connection):
        self.db_connection = db_connection
        self.ph = PasswordHasher()

    def authenticate_user(self, login: str = None, password: str = None) -> int | bool:
        #auth by login
        if (login is None) or (password is None):
            return False
        
        with self.db_connection.cursor() as cursor:
            #cursor.execute("SELECT id FROM users WHERE login = %s AND password = %s", (login, password))
            cursor.execute("SELECT id, password FROM users WHERE login = %s", (login,))
            res = cursor.fetchone()
            if res is None:
                return False
            id, pwd = res

            if self.ph.verify(pwd, password):
                return id
        
        return False

    def authenticate_user_by_tg(self, telegram_id: int) -> int | bool:
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
            res = cursor.fetchone()
            return res[0] if res is not None else False
        
        return False

    def get_authorization(self, identifier: Identifiers, value: int) -> bool:
        if identifier == Identifiers.ID:
            with self.db_connection.cursor() as cursor:
                cursor.execute("SELECT auth_status FROM users WHERE id = %s", (value,))
                result = cursor.fetchone()
                if result:
                    return result[0]
        if identifier == Identifiers.TELEGRAM_ID:
            with self.db_connection.cursor() as cursor:
                cursor.execute("SELECT auth_status FROM users WHERE telegram_id = %s", (value,))
                result = cursor.fetchone()
                if result:
                    return result[0]
        return False

    def set_authorization(self, identifier: Identifiers, value: int, auth_status: bool = False) -> bool:
        with self.db_connection.cursor() as cursor:
            status = False
            if identifier == Identifiers.ID:
                cursor.execute("UPDATE users SET auth_status = %s WHERE id = %s", (auth_status, value))
                status = cursor.rowcount > 0
            if identifier == Identifiers.TELEGRAM_ID:
                cursor.execute("UPDATE users SET auth_status = %s WHERE telegram_id = %s", (auth_status, value))
                status = cursor.rowcount > 0
            if status:
                self.db_connection.commit()
        return False

    def remember_user(self, id: int, telegram_id: int, status: bool = False) -> bool:
        with self.db_connection.cursor() as cursor:
            cursor.execute("UPDATE users SET telegram_id = %s WHERE id = %s", ((telegram_id if status else None), id))
            status = cursor.rowcount > 0

        if status: 
            self.db_connection.commit()
        else:
            self.db_connection.rollback()
        
        return status
