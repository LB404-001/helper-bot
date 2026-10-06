from http import client
from random import Random, random
import asyncio, time, uuid
import json
from anyio import open_process
import httpx
import websockets

class Comfy():
    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.host = host
        self.port = port
        self.connection = f"http://{host}:{port}"

    async def base_scene(self, positive_prompt: str, negative_prompt:str, model: str, on_progress=None):
        schema: dict = json.load(open("/home/lb404/Documents/projects/helper/agent/comfy/workflows/base_scene.json", "r"))
        schema["6"]["inputs"]["text"] = positive_prompt
        schema["7"]["inputs"]["text"] = negative_prompt
        schema["4"]["inputs"]["ckpt_name"] = model
        rnd = Random()
        schema["3"]["inputs"]["seed"] = rnd.randint(0, 999999999)
        uid = "123" #str(uuid.uuid4())

        async with httpx.AsyncClient(base_url=self.connection, timeout=120) as comfy:
            async with websockets.connect(f"ws://{self.host}:{self.port}/ws?clientId={uid}") as ws:

                r = await comfy.post("/prompt", json={"prompt": schema, "client_id": uid}, timeout=30)
                r.raise_for_status()
                prompt_id = r.json()["prompt_id"]

                #receive status
                while True:
                    out = await ws.recv()
                    if not isinstance(out, str):
                        continue

                    message = json.loads(out)
                    if message["type"] == "executing":
                        data = message["data"]
                        if data["node"] is None and data["prompt_id"] == prompt_id:
                            break
                    if message["type"] == "progress_state" and on_progress:
                        data = message["data"]
                        #логика сборки прогреса
                        st = ""
                        for k in data["nodes"]:
                            percent = round((data["nodes"][k]["value"] / data["nodes"][k]["max"]) * 100)
                            st += f"{k}: {percent}% | {data["nodes"][k]["state"]}\n"
                        await on_progress(st)
                    continue
                    
            h = await comfy.get(f"/history/{prompt_id}")

            data = h.json()
            images: dict = data[prompt_id]["outputs"]["25"]["images"]

            #download images
            img = []
            for output in images:
                r = await comfy.get(f"/view", params={"filename": output["filename"], "subfolder": output["subfolder"], "type": output["type"]})
                img.append(r.content)
            if len(img) > 0:
                return img[0]
            return False
