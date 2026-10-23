from unicodedata import numeric

import requests, websocket
from typing import Any

from celery import Celery, Task
import redis, json, httpx, websockets, uuid, os
from logging import Logger
from random import Random

from celery.signals import worker_process_init

TG = f"https://api.telegram.org/bot"

app = Celery(
    "worker", 
    broker="redis://localhost:6379/0"
    )

app.conf.task_routes = {"worker.generate_image": {"queue": "comfy"}}
app.conf.worker_prefetch_multiplier = 1  # не резервировать лишние задачи
app.conf.task_acks_late = True

comfy = {}

@worker_process_init.connect
def init_process(**kwargs):
    url = os.environ["COMFY_URL"].rstrip("/").lstrip("http://")
    s = requests.Session()

    s.get(f"http://{url}/system_stats", timeout=10).raise_for_status()  # health-check при старте

    comfy["url"]=url
    comfy["session"]=s
    comfy["client_id"]=str(uuid.uuid4())

    
def tg(token, method, *, files=None, timeout=30, **data):
    response = httpx.post(
        f"{TG}{token}/{method}",
        data=data,
        files=files,
        timeout=timeout,
    )
    return response.json()

@app.task(name="worker.generate_image", bind=True, time_limit=900, soft_time_limit=840)
def generate_image(
        self,
        bot_token: str,
        chat_id: int, 
        msg_id: int, 
        positive_prompt: str, 
        negative_prompt:str, 
        model: str
        ):
    

    schema: dict = json.load(open("/home/lb404/Documents/projects/helper/agent/comfy/workflows/base_scene.json", "r"))
    schema["6"]["inputs"]["text"] = positive_prompt
    schema["7"]["inputs"]["text"] = negative_prompt
    schema["4"]["inputs"]["ckpt_name"] = model
    rnd = Random()
    schema["3"]["inputs"]["seed"] = rnd.randint(0, 999999999)
    uid = str(uuid.uuid4())

    ws = websocket.WebSocket()
    ws.connect(f"ws://{comfy["url"]}/ws?clientId={uid}")

    r = requests.post(f"http://{comfy["url"]}/prompt", json={"prompt": schema, "client_id": uid}, timeout=30)
    r.raise_for_status()
    prompt_id = r.json()["prompt_id"]

        #receive status
    while True:
        out = ws.recv()
        if not isinstance(out, str):
            continue

        message = json.loads(out)
        if message["type"] == "executing":
            data = message["data"]
            if data["node"] is None and data["prompt_id"] == prompt_id:
                break
        if message["type"] == "progress_state":
            data = message["data"]
            #логика сборки прогреса
            st = ""
            for k in data["nodes"]:
                m = data["nodes"][k]["max"]
                if m > 0:
                    percent = round((data["nodes"][k]["value"] / m) * 100)
                else:
                    percent = 100
                st += f"{k}: {percent}% | {data["nodes"][k]["state"]}\n"
            tg(bot_token, "editMessageText", chat_id=chat_id, message_id=msg_id, text=st)
        continue
                
    h = requests.get(f"http://{comfy["url"]}/history/{prompt_id}")

    data = h.json()
    images: dict = data[prompt_id]["outputs"]["25"]["images"]

    #download images
    img = []
    for output in images:
        r = requests.get(
            f"http://{comfy["url"]}/view", 
            params={"filename": output["filename"], "subfolder": output["subfolder"], "type": output["type"]}
            )
        
        img.append(r.content)
        tg(
            bot_token, 
            "sendPhoto", 
            chat_id = chat_id,
            files={"photo": (output["filename"], r.content, "image/png")},
            timeout=60
            )
    tg(bot_token, "editMessageText", chat_id=chat_id, message_id=msg_id, text="Done")