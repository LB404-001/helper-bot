
class GPU_Manager: 
    def __init__(self):
        self.mode = None

    def llm_mode(self):
        self.mode = "llm"
        pass

    def comfy_mode(self):
        self.mode = "comfy"
        pass