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
    
    def delete_chat(self, chat_id: int, user_id: int) -> bool:
        with self.db_connection.cursor() as cursor:
            res = cursor.execute("DELETE FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id))
            self.db_connection.commit()
            return res.rowcount > 0

    def get_chats(self, user_id: int) -> dict:
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT id, title FROM chats WHERE user_id = %s", (user_id,))
            chats = cursor.fetchall()
            return {chat[0]: chat[1] for chat in chats} if chats else False  # Return a dictionary of chat names
    
    #Messages

    def get_messages(self, chat_id: int) -> list:
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT context FROM messages WHERE chat_id = %s", (chat_id,))
            messages = cursor.fetchall()
            return [message[0] for message in messages] if messages else []  # Return a list of messages
    
    def add_message(self, chat_id: int, context: str) -> bool:
        with self.db_connection.cursor() as cursor:
            res = cursor.execute("INSERT INTO messages (chat_id, context) VALUES (%s, %s)", (chat_id, context))
            self.db_connection.commit()
            return res.rowcount > 0
    
    def delete_message(self, message_id: int) -> bool:
        with self.db_connection.cursor() as cursor:
            res = cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
            self.db_connection.commit()
            return res.rowcount > 0
