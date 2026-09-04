from agent.llm import LLM

class Core:
    def __init__(self, llm: LLM):
        self.llm = llm
    
    def process_message(self, message: str) -> str:
        #print("Processing message:", message)
        response = self.llm.generate_response(message)
        #print("Generated response:", response)
        return response