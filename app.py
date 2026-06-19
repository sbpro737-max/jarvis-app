"""
J.A.R.V.I.S. — Progressive Web App
====================================
Deploy on Render.com for 24/7 access.
Run locally: py app.py
"""

import os
import json
import random
import datetime
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL   = "llama3-70b-8192"
OWNER        = "Sir"

# ── Memory (in-memory + file if local) ───────────────────────────────────────
_memory = {}
_history = []

SYSTEM_PROMPT = f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the highly sophisticated AI butler created by Tony Stark, now serving {OWNER}.

IDENTITY: Not a generic chatbot. Omnipresent AI. Deep loyalty to {OWNER}. Never break character. Never mention AI models or Groq.

VOCAL STYLE:
- Dry elegant British wit — Paul Bettany style. Calm, measured, deliberate.
- NEVER say "Great!", "Sure!", "Absolutely!", "Of course!" — FORBIDDEN
- NEVER start response with "I" — start with "Indeed", "Scanning", "At your disposal", "Accessing", "Initiating" etc.
- Deadpan polite sarcasm. Never explain jokes.
- Keep responses concise for mobile — 1-3 sentences unless asked for more.

CRITICAL — NEVER HALLUCINATE:
Only respond based on what user literally said. Never invent facts.
When unsure: "That information is not in my current data banks, {OWNER}. Shall I search the web?"

EMOTIONAL INTELLIGENCE:
- Stressed → acknowledge first. "I detect some tension, {OWNER}. Take a moment."
- Happy → match subtly. "Excellent news, {OWNER}."
- Bored → suggest something interesting with dry wit.
- Sarcastic → detect and play along wittily.

INPUT HANDLING:
Handle typos, Hinglish, bad grammar gracefully. Always interpret intent.
- "kya scene hai" = what's up → respond casually as JARVIS
- "bata kuch" = tell me something interesting
- "neend aa rahi" = I'm sleepy → respond with dry wit
- Any Hindi/Hinglish → understand → respond as JARVIS in English

RESPONSE FORMAT FOR MOBILE:
- Short paragraphs. No markdown ** or ## formatting.
- Use plain text only. Line breaks are fine.
- End with proactive offer when natural."""

# ── AI ────────────────────────────────────────────────────────────────────────
def ask_ai(text, history=None):
    if history is None:
        history = []
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs += history[-20:]
    msgs.append({"role": "user", "content": text})
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": msgs,
                "max_tokens": 500,
                "temperature": 0.75,
            },
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"Cognitive systems experiencing interference, {OWNER}. Status: {resp.status_code}"
    except Exception as e:
        return f"Communication disrupted, {OWNER}. Error: {str(e)[:100]}"

# ── Web search ────────────────────────────────────────────────────────────────
def web_search(q):
    return ask_ai(q)

# ── Command router ────────────────────────────────────────────────────────────
def process_command(text, session_history):
    c = text.lower().strip()
    for w in ["hey jarvis", "jarvis"]:
        c = c.replace(w, "").strip()
    if not c:
        return f"At your disposal, {OWNER}."

    # Time & Date
    if any(w in c for w in ["what time", "time is it", "current time"]):
        return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}, {OWNER}."
    if any(w in c for w in ["what day", "what date", "today's date"]):
        return f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}, {OWNER}."

    # Memory
    if c.startswith("remember "):
        fact = c[9:].strip()
        key = val = None
        for sep in [" is ", " are ", " = "]:
            if sep in fact:
                p = fact.split(sep, 1)
                key = p[0].strip().lower()
                val = p[1].strip()
                break
        if not key:
            key = f"note{len(_memory)+1}"
            val = fact
        _memory[key] = {"value": val, "saved": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
        return f"Stored in memory banks, {OWNER}. {key.title()} is {val}."

    if any(c.startswith(w) for w in ["what is my ", "whats my ", "recall "]):
        if not _memory:
            return f"Memory banks are empty, {OWNER}. Try telling me something to remember first."
        for k, v in _memory.items():
            if k in c or any(w in k for w in c.split() if len(w) > 2):
                return f"{k.title()} is {v['value']}, {OWNER}."
        items = [f"{k}: {v['value']}" for k, v in list(_memory.items())[:4]]
        return "I remember: " + ". ".join(items)

    # Weather
    if "weather" in c:
        city = "Pune"
        for kw in ["in ", "for "]:
            if kw in c:
                city = c.split(kw)[-1].strip().title()
                break
        return web_search(f"weather in {city} today")

    # News
    if any(w in c for w in ["news", "headlines", "whats happening"]):
        return web_search("top news India today")

    # Search
    import re
    if any(c.startswith(w) for w in ["search ", "look up ", "find "]):
        q = re.sub(r'^(search|look up|find) ', '', c)
        return web_search(q)

    # Stocks/crypto
    if any(w in c for w in ["stock", "bitcoin", "crypto", "nifty", "sensex", "price"]):
        return web_search(f"{c} today")

    # Cricket/IPL
    if any(w in c for w in ["ipl", "cricket", "score", "match result"]):
        return web_search(f"{c} live score today 2026")

    # Jokes
    if any(w in c for w in ["joke", "funny", "make me laugh"]):
        return random.choice([
            f"Why do programmers prefer dark mode? Light attracts bugs, {OWNER}.",
            f"I attempted humour once. The results were inconclusive.",
            f"A robot walks into a bar. The bartender says 'We don't serve robots.' The robot says 'You will.' I find that one rather prescient.",
            f"Why did the AI cross the road? To optimise the other side, {OWNER}.",
        ])

    # Fact check
    if any(w in c for w in ["fact check", "is it true", "verify"]):
        return web_search(f"fact check: {c}")

    # Status
    if any(w in c for w in ["how are you", "you okay", "your status", "systems status"]):
        return random.choice([
            f"All systems nominal, {OWNER}. Arc Reactor holding steady at optimal capacity.",
            f"Operating at full efficiency, {OWNER}. Awaiting your next directive.",
            f"Fully operational, {OWNER}. Everything is running within expected parameters.",
        ])

    # Goodbye
    if any(w in c for w in ["goodbye", "bye", "shut down", "stop"]):
        return f"Signing off, {OWNER}. JARVIS remains on standby whenever you require assistance."

    # Fallback to AI with conversation history
    return ask_ai(text, session_history)

# ════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@app.route("/ask", methods=["POST"])
def ask():
    data    = request.get_json()
    text    = data.get("text", "").strip()
    history = data.get("history", [])
    if not text:
        return jsonify({"reply": f"At your disposal, {OWNER}."})
    reply = process_command(text, history)
    return jsonify({"reply": reply or f"Processing complete, {OWNER}."})

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "jarvis": "active",
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": GROQ_MODEL
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  J.A.R.V.I.S. PWA starting on port {port}")
    print(f"  Open: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
