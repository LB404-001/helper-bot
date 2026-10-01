from random import Random, random
import asyncio, time
import json
import httpx

class Comfy():
    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.host = host
        self.port = port
        self.connection = f"http://{host}:{port}"

    async def base_scene(self, positive_prompt: str, negative_prompt:str):
        schema: dict = json.load(open("/home/lb404/Documents/projects/helper/agent/comfy/workflows/base_scene.json", "r"))
        schema["6"]["inputs"]["text"] = positive_prompt
        schema["7"]["inputs"]["text"] = negative_prompt
        rnd = Random()
        schema["3"]["inputs"]["seed"] = rnd.randint(-999999999, 999999999)

        async with httpx.AsyncClient(base_url=self.connection, timeout=120) as comfy:
            r = await comfy.post("/prompt", json={"prompt": schema}, timeout=30)
            r.raise_for_status()
            prompt_id = r.json()["prompt_id"]

            loop = asyncio.get_event_loop()
            start = loop.time()

            #pooling history
            while time.monotonic() < time.monotonic() + 365:
                h = await comfy.get(f"/history/{prompt_id}")
                r.raise_for_status()
                data = h.json()
                if prompt_id in data:
                    #return data[prompt_id]
                    images: dict = data[prompt_id]["outputs"]["25"]["images"]
                    break
                if loop.time() - start > 360:
                    raise TimeoutError("ComfyUI не ответил вовремя")
                await asyncio.sleep(1)

            #download image
            img = []
            for output in images:
                r = await comfy.get(f"/view", params={"filename": output["filename"], "subfolder": output["subfolder"], "type": output["type"]})
                img.append(r.content)
            if len(img) > 0:
                return img[0]
            return False
