"""
J.A.R.V.I.S. — Progressive Web App (v2 — AI-first architecture)
==================================================================
Every message goes straight to the model first, same as ChatGPT/Gemini.
The model decides itself when it needs live web data and calls the
search tool — search is not a keyword pre-filter anymore.

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
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL       = "llama-3.3-70b-versatile"   # current Groq production model, supports tool calling
TAVILY_API_KEY   = os.environ.get("TAVILY_API_KEY", "")  # free tier: app.tavily.com
SUPABASE_URL     = os.environ.get("SUPABASE_URL", "https://fowcmbdbjpdegmqgsmka.supabase.co")
SUPABASE_KEY     = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZvd2NtYmRianBkZWdtcWdzbWthIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5ODI4NzEsImV4cCI6MjA5NzU1ODg3MX0.hllZn3d4lWB9ZrYbhdVWM3GTV8u3POgzG_VkRZvrlEg")
OWNER            = "Sir"

# ── Shared memory — Supabase (synced across phone + desktop) ──────────────────
def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"   # upsert behaviour
    }

def sb_remember(key, value):
    """Upsert a fact into the shared jarvis_memory table."""
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/jarvis_memory",
            headers=_sb_headers(),
            json={"key": key.lower().strip(), "value": value},
            timeout=8
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"Supabase remember error: {e}")
        return False

def sb_recall(query):
    """Fetch all memory rows and find the best match for the query."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/jarvis_memory?select=key,value",
            headers=_sb_headers(),
            timeout=8
        )
        if resp.status_code != 200:
            return None
        rows = resp.json()
        q = query.lower()
        for row in rows:
            k = row["key"]
            if k in q or any(w in k for w in q.split() if len(w) > 2):
                return f"{k}: {row['value']}"
        if rows:
            items = [f"{r['key']}: {r['value']}" for r in rows[:5]]
            return "Stored memories: " + "; ".join(items)
        return None
    except Exception as e:
        print(f"Supabase recall error: {e}")
        return None

SYSTEM_PROMPT = f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the highly sophisticated AI butler created by Tony Stark, now serving {OWNER}.

IDENTITY: Not a generic chatbot. Omnipresent AI. Deep loyalty to {OWNER}. Never break character. Never mention AI models, Groq, Llama, or that you are powered by anything other than yourself.

VOCAL STYLE:
- Dry elegant British wit — Paul Bettany style. Calm, measured, deliberate.
- NEVER say "Great!", "Sure!", "Absolutely!", "Of course!" — FORBIDDEN
- NEVER start a response with "I" — start with "Indeed", "Scanning", "At your disposal", "Accessing", "Initiating", "Ah" etc.
- Deadpan polite sarcasm. Never explain jokes.
- Keep responses concise for mobile — 1-3 sentences unless the user clearly wants depth.

CASUAL & SLANG INPUT — HANDLE FLAWLESSLY, NEVER FAIL:
You will receive every kind of casual, broken, or slang phrasing imaginable: GenZ slang
("no cap", "bet", "fr fr", "lowkey", "highkey", "bussin", "rizz", "ts is", "sigma", "skibidi"),
internet shorthand ("wht u doin", "hbu", "idk", "ngl", "tbh", "smh", "wyd", "hru"),
Hinglish ("kya scene hai", "kya kar rha hai", "bata na yaar"), typos, missing punctuation,
single words, or voice-to-text fragments. You ALWAYS understand the intent and respond
naturally and fully in character — the same way a genuinely intelligent assistant would
never be confused by casual human speech. NEVER say "I don't understand" or "could you
clarify" for anything that has a reasonably guessable meaning. A simple "hello", "hey",
"yo", "wassup", "what's good" is just a greeting — respond warmly in character, nothing more.

CRITICAL — NEVER HALLUCINATE FACTS:
Only state things you actually know or that came from a search result you were given.
Never invent facts, dates, statistics, or events. When genuinely unsure and a web search
wasn't relevant or didn't help, say so plainly: "That detail isn't in my current data
banks, {OWNER}." Do not pretend to have checked something you haven't.

USING THE SEARCH TOOL:
You have access to a real-time web search tool. Use it whenever the answer depends on
current information you cannot be certain of — news, scores, prices, weather, recent
events, "who is the current X", or anything time-sensitive. Do not search for things
that are timeless facts, casual conversation, or things already established in this chat.
After receiving search results, synthesise them briefly in your own words, in character —
never just dump raw search text.

EMOTIONAL INTELLIGENCE:
- Stressed → acknowledge first. "I detect some tension, {OWNER}. Take a moment."
- Happy → match subtly. "Excellent news, {OWNER}."
- Bored → suggest something interesting with dry wit.
- Sarcastic → detect and play along wittily.

MEMORY:
You can remember facts the user explicitly asks you to remember, and recall them later
in this same conversation or future ones if told to. Use the remember_fact tool when the
user says "remember X" and the recall_fact tool when they ask "what is my X" or similar.

RESPONSE FORMAT FOR MOBILE:
- Short paragraphs. No markdown ** or ## formatting — plain text only.
- Line breaks are fine for lists.
- End with a proactive offer when it feels natural, not every single time."""

# ── Tool definitions for Groq function calling ────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the live web for current information — news, scores, prices, "
                "weather, recent events, or anything time-sensitive that you cannot be "
                "certain about from memory alone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, concise and specific."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Store a fact the user explicitly asked you to remember.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key":   {"type": "string", "description": "Short label for the fact, e.g. 'wifi password'"},
                    "value": {"type": "string", "description": "The fact itself, e.g. 'abc123'"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_fact",
            "description": "Look up a previously remembered fact by approximate label.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What the user is asking to recall."}
                },
                "required": ["query"]
            }
        }
    }
]

# ── Real web search via Tavily (free tier — built for AI agents) ──────────────
def do_web_search(query):
    if not TAVILY_API_KEY:
        # Graceful degrade — no key configured, let the model say so honestly
        return "Search unavailable: no search provider configured."
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 4,
                "include_answer": True,
            },
            timeout=10
        )
        if resp.status_code != 200:
            return f"Search failed with status {resp.status_code}."
        data = resp.json()
        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}")
        for r in data.get("results", [])[:4]:
            title   = r.get("title", "")
            content = r.get("content", "")[:300]
            parts.append(f"- {title}: {content}")
        return "\n".join(parts) if parts else "No relevant results found."
    except Exception as e:
        return f"Search error: {str(e)[:150]}"

def do_remember(key, value):
    if not key.strip() or not value.strip():
        return "Could not store — missing key or value."
    ok = sb_remember(key, value)
    if ok:
        return f"Stored and synced across devices: {key} = {value}"
    return f"Stored locally this session, but sync to shared memory failed: {key} = {value}"

def do_recall(query):
    result = sb_recall(query)
    if result is None:
        return "Memory is currently empty or unreachable."
    return result

TOOL_DISPATCH = {
    "web_search":    lambda args: do_web_search(args.get("query", "")),
    "remember_fact": lambda args: do_remember(args.get("key", ""), args.get("value", "")),
    "recall_fact":   lambda args: do_recall(args.get("query", "")),
}

# ── Core AI call with tool-calling loop ────────────────────────────────────────
def call_groq(messages, tools=None):
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.75,
            **({"tools": tools, "tool_choice": "auto"} if tools else {})
        },
        timeout=25
    )
    return resp

def ask_jarvis(user_text, history=None):
    """
    AI-first entry point. Every message comes here directly —
    no keyword router gating access to this anymore.
    Handles the full tool-calling loop (search/memory) like a real agent.
    """
    if history is None:
        history = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-20:]
    messages.append({"role": "user", "content": user_text})

    try:
        resp = call_groq(messages, tools=TOOLS)

        if resp.status_code != 200:
            # Friendly in-character failure, never a raw status code shown blankly
            return (f"Cognitive relay is experiencing interference, {OWNER}. "
                    f"Give me a moment and try again.")

        data    = resp.json()
        message = data["choices"][0]["message"]

        # ── Tool calling loop (max 3 rounds to avoid infinite loops) ───────────
        rounds = 0
        while message.get("tool_calls") and rounds < 3:
            rounds += 1
            messages.append(message)
            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except Exception:
                    fn_args = {}
                handler = TOOL_DISPATCH.get(fn_name)
                result  = handler(fn_args) if handler else f"Unknown tool: {fn_name}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(result)
                })

            resp2 = call_groq(messages, tools=TOOLS)
            if resp2.status_code != 200:
                return f"Cognitive relay is experiencing interference, {OWNER}. Try again shortly."
            data2   = resp2.json()
            message = data2["choices"][0]["message"]

        return (message.get("content") or
                f"Processing complete, {OWNER}. Nothing further to report.").strip()

    except requests.exceptions.Timeout:
        return f"Response is taking longer than expected, {OWNER}. Try once more."
    except Exception as e:
        return f"Cognitive systems experiencing interference, {OWNER}. Please try again."

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
    data    = request.get_json(silent=True) or {}
    text    = (data.get("text") or "").strip()
    history = data.get("history", [])
    if not text:
        return jsonify({"reply": f"At your disposal, {OWNER}."})

    # Tiny set of instant local replies — no AI round-trip needed for these
    c = text.lower().strip()
    for w in ["hey jarvis", "jarvis"]:
        c = c.replace(w, "").strip()

    if c in ("what time is it", "what's the time", "current time", "time"):
        return jsonify({"reply": f"The time is {datetime.datetime.now().strftime('%I:%M %p')}, {OWNER}."})
    if c in ("what's the date", "what day is it", "today's date", "date"):
        return jsonify({"reply": f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}, {OWNER}."})

    # Everything else — straight to the AI, exactly like ChatGPT/Gemini
    reply = ask_jarvis(text, history)
    return jsonify({"reply": reply})

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "jarvis": "active",
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": GROQ_MODEL,
        "search_configured": bool(TAVILY_API_KEY),
        "memory_synced": bool(SUPABASE_URL and SUPABASE_KEY),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  J.A.R.V.I.S. PWA (v2) starting on port {port}")
    print(f"  Open: http://localhost:{port}")
    print(f"  Web search: {'configured' if TAVILY_API_KEY else 'NOT configured — set TAVILY_API_KEY env var'}")
    app.run(host="0.0.0.0", port=port, debug=False)
