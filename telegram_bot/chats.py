import psycopg
#test

class Chats:
    def __init__(self, db_connection: psycopg.Connection):
        self.db_connection = db_connection

    def add_chat(self, chat_name: str, user_id: int) -> bool:
        with self.db_connection.cursor() as cursor:
            chat = cursor.execute("SELECT * FROM chats WHERE chat_name = %s AND user_id = %s", (chat_name, user_id))
            if cursor.fetchone():
                return False  # Chat already exists
            res = cursor.execute("INSERT INTO chats (chat_name, user_id) VALUES (%s, %s)", (chat_name, user_id))
            self.db_connection.commit()
            return res.rowcount > 0