import psycopg
import enum

class Identifiers(enum.Enum):
    ID = "id"
    TELEGRAM_ID = "telegram_id"

class Authorization:
    def __init__(self, db_connection: psycopg.Connection):
        self.db_connection = db_connection

    def authenticate_user(self, login: str, password: str) -> bool:
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE login = %s AND password = %s", (login, password))
            return cursor.fetchone() is not None

    def deauthenticate_user(self, login: str, password: str) -> bool:
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE login = %s AND password = %s", (login, password))
            user = cursor.fetchone()
            if user:
                cursor.execute("UPDATE users SET auth_status = %s WHERE login = %s AND password = %s", (False, login, password))
                return cursor.rowcount > 0
        return False

    def get_authorization(self, identifier: Identifiers, value: int) -> bool:
        if identifier == Identifiers.ID:
            with self.db_connection.cursor() as cursor:
                cursor.execute("SELECT auth_status FROM users WHERE id = %s", (value,))
                result = cursor.fetchone()
                if result:
                    return result[0]
        return False

    def set_authorization(self, identifier: Identifiers, value: int, status: bool = False) -> bool:
        if identifier == Identifiers.ID:
            with self.db_connection.cursor() as cursor:
                cursor.execute("UPDATE users SET auth_status = %s WHERE id = %s", (status, value))
        if identifier == Identifiers.TELEGRAM_ID:
            with self.db_connection.cursor() as cursor:
                cursor.execute("UPDATE users SET auth_status = %s WHERE telegram_id = %s", (status, value))
                return cursor.rowcount > 0
        return False

    def remember_user(self, id: int, telegram_id: int, status: bool = False) -> bool:
        with self.db_connection.cursor() as cursor:
            cursor.execute("UPDATE users SET telegram_id = %s WHERE id = %s", ((telegram_id if status else "NULL"), id))
            return cursor.rowcount > 0
