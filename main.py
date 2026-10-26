
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import os, json, requests, re, sys, logging


load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


app = FastAPI(title="Spam Filtration - Groq backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


HERE = Path(__file__).parent.resolve()
INDEX_FILE = HERE / "index.html"


logger.info(f"Starting Spam Filtration app. Project folder: {HERE}")
logger.info(f"Index exists: {INDEX_FILE.exists()} -> {INDEX_FILE}")


@app.get("/", include_in_schema=False)
def root():
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE), media_type="text/html")
    return JSONResponse(status_code=404, content={"detail": "index.html not found on server"})


class ClassifyRequest(BaseModel):
    text: str


SYSTEM_PROMPT = """
You are an expert message classifier. You MUST RETURN ONLY valid JSON (no extra commentary).
Schema:
{
  "label": "<spam|safe|promotional>",
  "confidences": {"spam": float, "safe": float, "promotional": float}
}
Rules:
- If message contains classic scam phrases like "you won", "free prize", "click here to claim", "congratulations, you won", "claim your prize" then label "spam".
- If it's clearly marketing (offers with unsubscribe/store names, coupon codes, promotional language) label "promotional".
- Otherwise label "safe".
- Confidences must be floats summing to 1.0. For rule-matched spam, prefer high confidence (>= 0.90).
"""


SPAM_KEYWORDS = [
    r"you won", r"free prize", r"click here", r"claim (your )?prize",
    r"congratulations", r"won a .*prize", r"free iphone", r"urgent .* account",
    r"claim your prize", r"click to claim", r"click here to claim",
]

def rule_based_check(text: str):
    t = (text or "").lower()
    for pat in SPAM_KEYWORDS:
        if re.search(pat, t):
            return {"label": "spam", "confidences": {"spam": 0.95, "safe": 0.03, "promotional": 0.02}}
    return None


def parse_model_json(model_text: str):
    try:
        return json.loads(model_text)
    except Exception:
        m = re.search(r"(\{.*\})", model_text, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
        return None


@app.post("/classify")
def classify(req: ClassifyRequest):
    
    rule = rule_based_check(req.text)
    if rule:
        return {"label": rule["label"], "confidences": rule["confidences"], "raw_model_output": None, "reason": "rule_match"}

    
    if not GROQ_API_KEY:
        
        return JSONResponse(status_code=503, content={
            "error": "GROQ_API_KEY is not configured on the server. Set an env var or add a .env file.",
            "example_env": ".env.example"
        })

    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.text}
    ]

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 300
    }

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}


    try:
        res = requests.post(GROQ_CHAT_URL, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error contacting Groq API: {str(e)}")

    if res.status_code != 200:
        logger.error("Groq API returned %s : %s", res.status_code, res.text[:1000])
        raise HTTPException(status_code=502, detail=f"Groq API returned {res.status_code}: {res.text[:1000]}")

    data = res.json()

    
    model_text = ""
    try:
        model_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        model_text = str(data)

    parsed = parse_model_json(model_text)
    if not parsed:
        logger.warning("Failed to parse JSON from model output: %s", model_text)
        return {
            "label": "unknown",
            "confidences": {"spam": 0.0, "safe": 0.0, "promotional": 0.0},
            "raw_model_output": data,
            "error": "Could not parse JSON from model output"
        }

    
    conf = parsed.get("confidences", {})
    normalized = {}
    for k in ("spam", "safe", "promotional"):
        try:
            normalized[k] = float(conf.get(k, 0.0))
        except Exception:
            normalized[k] = 0.0
    s = sum(normalized.values())
    if s <= 0:
        normalized = {"spam": 0.33, "safe": 0.33, "promotional": 0.34}
    else:
        normalized = {k: v / s for k, v in normalized.items()}

    return {"label": parsed.get("label", "unknown"), "confidences": normalized, "raw_model_output": data}


@app.on_event("startup")
def startup_event():
    
    if not GROQ_API_KEY:
        logger.info("GROQ_API_KEY is NOT configured — Groq model calls will not work without it. Rule-based checks still work.")
    else:
        logger.info("GROQ_API_KEY is present. Groq model calls enabled.")
