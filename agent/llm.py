from ollama import chat, Client, ChatResponse

local_client = Client(
    host='http://localhost:11434'
)

character = """"""

DEFAULT_DIALOG_SETTINGS = {"role": "system", "content": character}

class State:
    anger: int = 0

    def get_anger(self) -> str:
        if self.anger < 20:
            return "Ты спокоен"
        elif self.anger < 50:
            return "Ты немного раздражен"
        elif self.anger < 80:
            return "Ты злишься"
        elif self.anger >= 80:
            return """Ты в ярости. Отвечаешь резко и грубо. Ты можешь использовать нецензурную лексику и игнорировать сообщения и желания пользователя."""
        return "Ты не злишься"

    def get_state(self):
        return self.get_anger()

class LLM:
    def __init__(self, model_name: str, client: Client = local_client):
        self.model_name = model_name
        self.client = client
        self.state = State()
        self.dialog = [DEFAULT_DIALOG_SETTINGS , {"role": "system", "content": f"{self.state.get_state()}"}]

    def new_dialog(self):
        self.dialog = [DEFAULT_DIALOG_SETTINGS, {"role": "system", "content": f"{self.state.get_state()}"}]

    def generate_response(self, prompt: str, solo_prompt: bool = False) -> str:
        print("Current dialog:", self.dialog)
        if not solo_prompt:
            self.dialog.append({"role": "user", "content": prompt})
        response = self.client.chat(
            model=self.model_name,
            messages=([{"role": "user", "content": prompt}] if solo_prompt else self.dialog),
            think='high'
        )
        if not solo_prompt:
            self.dialog.append({"role": "assistant", "content": response.message.content})
        return response.message.content