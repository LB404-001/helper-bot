import psycopg
import enum

class Sessions:
    def __init__(self, db_connection: psycopg.Connection):
        self.db_connection = db_connection
    
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
    
    def check_session(self, token: str) -> int | None:
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT user_id FROM sessions WHERE token = %s", (token,))
            res = cursor.fetchone()
            return None if res is None else res[0]
        return None