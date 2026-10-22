from collections import deque
from datetime import date
from flask import Flask, request, jsonify
import json
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.utils.json import parse_json_markdown
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
import logging
from logging.handlers import RotatingFileHandler
import os
import pyttsx3

import threading
import time

MODEL_BAME = "gemini-2.5-flash-lite"

# 1. Create a logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 2. Create the rotating file handler
handler = RotatingFileHandler(
    "llm_service.log", 
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=2
)

# 3. Create a logging format
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(formatter)

# 4. Add the handler to the logger
logger.addHandler(handler)

# Set your custom process name here


def safe_parse_llm_json(response):
    """
    Extracts and parses JSON from a string that might contain 
    markdown code blocks (```json ... ```) or extra whitespace.
    """
    if isinstance(response, AIMessage):
        text = response.content
    else:
        text = str(response)
        
    try:
        # This handles the ```json ... ``` wrapper automatically
        return parse_json_markdown(text)
    except Exception as e:
        logging.error(f"Failed to parse JSON: {text[:100]}... Error: {e}")
        return {"error": "Invalid JSON format", "raw": text}

class LLMModule:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=MODEL_BAME,
            response_mime_type="application/json",
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )

        self.llmTxtOnly = ChatGoogleGenerativeAI(
            model=MODEL_BAME,
            response_mime_type="text/plain",
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )

        self.chain = self.llm | JsonOutputParser()

        logging.info(f"LLMModule initialized with model {MODEL_BAME}")

    def invoke(self, res):
        try:
            if 'type' not in res and 'prompt' in res:
                logging.info(f"Invoking LLM with text prompt")
                response = self.llm.invoke(res.get("prompt"))
                parsed_data = safe_parse_llm_json(response)
                return parsed_data

                # return self.chain.invoke(res.get("prompt")) #this sometimes gives json parsing error
            elif 'type' in res and res['type'] == 'TextReply':
                logging.info(f"Invoking LLM with TextReply prompt")
                message = HumanMessage(
                    content=res.get("prompt")
                )
                return self.llmTxtOnly.invoke([message])
            elif 'type' in res and res['type'] == 'HumanMessage':                    
                logging.info(f"Invoking LLM with HumanMessage prompt")
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": res.get("prompt")},
                        {
                            "type": "media",
                            "source_type": "base64",
                            "mime_type": res.get("mime_type", "application/pdf"),
                            "data": res.get("pdf_base64", None)
                        },
                    ]
                )
                return self.chain.invoke([message]) 
            else:
                logging.error(f"Invalid request format: {res}")
                return {'error': "Invalid request format"} 
        except Exception as e:
            logging.error(f"Error invoking LLM: {str(e)}")
            return {'error': f"An error occurred while invoking LLM: {str(e)}"}

class BlockingRateLimiter:
    def __init__(self, max_calls=5, period=60, min_interval=8):
        self.max_calls = max_calls
        self.period = period
        self.min_interval = min_interval
        self.lock = threading.Lock()
        self.calls = deque()
        self.last_call_ts = None

    def acquire(self):
        """
        Blocks until a slot is available.
        """
        while True:
            with self.lock:
                now = time.time()

                # Min gap between calls
                if self.last_call_ts is not None:
                    gap = now - self.last_call_ts
                    if gap < self.min_interval:
                        wait_time = self.min_interval - gap
                        # Release lock before sleeping
                        pass
                    else:
                        wait_time = 0
                else:
                    wait_time = 0

                if wait_time ==0:
                    # Remove calls older than period
                    while self.calls and now - self.calls[0] > self.period:
                        self.calls.popleft()

                    if len(self.calls) < self.max_calls:
                        # slot available
                        self.calls.append(now)
                        return
                    
            # Sleep outside the lock
            if wait_time > 0:
                time.sleep(wait_time)
            else:
                time.sleep(0.5)


class Utterance():
    def __init__(self):    
        self.voice_engine = pyttsx3.init()
        # voices = self.voice_engine.getProperty('voices')
        # self.voice_engine.setProperty('voice', self.voice_engine.getProperty('voices')[2].id)
        self.say("Starting voice engine service.")
        logging.info("Voice engine initialized and started.")

    def say (self, text):
        t1 = threading.Thread(target = self.thTalk, args = (text, ) )
        t1.start()
        
    def thTalk (self, text): 
        try:
            if self.voice_engine._inLoop:
                self.voice_engine.endLoop()
                time.sleep(0.1)
            if not self.voice_engine._inLoop:
                self.voice_engine.startLoop(False)
                time.sleep(0.1)
        except Exception as e:
            logging.error(f"Error refreshing voice engine loop: {str(e)}")
            return False

        try:
            self.voice_engine.setProperty('rate', 180)  # Setting up new voice rate
            self.voice_engine.setProperty('volume', 1.0)  # Setting up volume level  between 0 and 1
            self.voice_engine.setProperty('voice', "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-US_ZIRA_11.0")
            self.voice_engine.say(text)   
            logging.info(f"Uttering text: {text}")
            time.sleep(0.1)
            self.voice_engine.iterate()
        except Exception as e:
            logging.error(f"Error in utterance: {str(e)}")
            return False
                    
        return True
           
class DailyUsageTracker:
    def __init__(self, path="llm_usage.json", limit=200):
        self.path = path
        self.limit = limit
        self.data = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self.data = json.load(f)
            except Exception as e:
                logging.error(f"Failed to load usage file: {e}")
                self.data = {}

        # Old codes before issues with date handling
        # today = date.today().isoformat()
        # if os.path.exists(self.path):
        #     with open(self.path, "r") as f:
        #         data = json.load(f)
        #     if data.get("date") == today:
        #         self.date = today
        #         self.count = data.get("count", 0)
        #         self.last_warned = data.get("last_warned", 0)
        #         return

        # # reset for new day
        # self.date = today
        # self.count = 0
        # self.last_warned = 0
        # self._persist()

    def _get_today_record(self):
        today = date.today().isoformat()
        # If the date changes (e.g. midnight crossed or system woke from hibernation)
        if today not in self.data:
            self.data[today] = {"count": 0, "last_warned": 0}
            self._persist()
        return self.data[today]

    def _persist(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to persist usage file: {e}")

    def _get_today_record(self):
        today = date.today().isoformat()
        # If the date changes (e.g. midnight crossed or system woke from hibernation)
        if today not in self.data:
            self.data[today] = {"count": 0, "last_warned": 0}
            self._persist()
        return self.data[today]

    def increment(self):
        record = self._get_today_record()
        record["count"] += 1
        self._persist()
        return record["count"]

    def should_warn(self):
        record = self._get_today_record()
        count = record["count"]
        last_warned = record["last_warned"]
        return (
            count >= 150 and
            count <= self.limit and
            count - last_warned >= 50
        )

    def mark_warned(self):
        record = self._get_today_record()
        record["last_warned"] = record["count"]
        self._persist()

try:
    app = Flask(__name__)
    llm = LLMModule()
    limiter = BlockingRateLimiter(max_calls=5, period=60)
    speaking = Utterance()    
    usage_tracker = DailyUsageTracker()
    logging.info("FastAPI app for Jarvis service initialized")
except Exception as e:
    logging.error(f"Error initializing FastAPI app: {str(e)}")

@app.route("/invoke", methods=["POST"])
def invoke_llm():
    limiter.acquire()  # blocks until permit available
    try:       
        body = request.get_json()
        usage = usage_tracker.increment()

        if usage_tracker.should_warn():
            speaking.say(f"Warning: {usage} LLM calls used.")
            usage_tracker.mark_warned()
            
        result = llm.invoke(body)
        if 'type' in body and body['type'] == 'TextReply':
            logging.info(f"Returning TextReply response")
            return result.content, 200

        if isinstance(result, dict) and 'error' in result:
            logging.error(f"Raising http error 400, with error invoking LLM: {str(result)}")
            return jsonify({"error": str(result)}), 400 
    
        return result
    except Exception as e:
        logging.error(f"Raising http error 500, unexpected error in /invoke: {str(e)}")
        return jsonify({"error": str(e)}), 500 

@app.route("/say", methods=["POST"])
def say():
    try:       
        body = request.get_json()
        if 'text' not in body:
            return jsonify({"error": "Missing text in the request body"}), 400 
            # raise HTTPException(status_code=400, detail="Missing 'text' in request body")
        speaking.say(body['text'])
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Raising http error 500, unexpected error in /say: {str(e)}")
        return jsonify({"error": str(e)}), 500 
        # raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=True, threaded=True)

