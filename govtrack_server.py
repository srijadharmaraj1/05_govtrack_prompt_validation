import asyncio
import json
import os
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pydantic import ValidationError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from models import GovTrackProfile
from prompt_helper import build_qualified_extraction_prompt

# ── Load .env 
load_dotenv(Path(__file__).parent / ".env")

SERPER_API_KEY     = os.getenv("SERPER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")
DASHBOARD_URL      = "http://localhost:3001"
DATA_FILE          = Path(__file__).parent / "data" / "profiles.json"

# ── Validate keys on startup ────
if not SERPER_API_KEY:
    raise ValueError("SERPER_API_KEY missing in .env")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY missing in .env")

# ── Ensure data dir + file exist 
DATA_FILE.parent.mkdir(exist_ok=True)
if not DATA_FILE.exists():
    DATA_FILE.write_text(json.dumps({"profiles": [], "last_updated": ""}, indent=2))

app = Server("govtrack-Tamil Nadu")

# ── DB helpers 
def load_db() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))

def save_db(db: dict):
    db["last_updated"] = datetime.now().isoformat()
    DATA_FILE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")



# OpenRouter — AI extraction from raw search snippets
# Model: mistralai/mistral-7b-instruct:free  (free tier on OpenRouter)

async def extract_with_openrouter(query: str, snippets: list) -> dict:
    """
    Send raw Google search snippets to OpenRouter (Mistral free model).
    The model extracts a clean structured JSON profile.
    This replaces the old brittle regex extraction.
    """
    prompt = build_qualified_extraction_prompt(query, snippets)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "GovTrack Tamil Nadu"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500
            }
        )

    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if model ignores instructions
    if "```" in raw_text:
        parts = raw_text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw_text = part
                break

    try:
        extracted = json.loads(raw_text)
    except json.JSONDecodeError:
        # Graceful fallback — return minimal profile
        extracted = {
            "name": "Extraction failed",
            "role": query,
            "cadre": None,
            "batch_year": None,
            "district": None,
            "state": "Tamil Nadu",
            "department": None,
            "party": None,
            "office_phone": None,
            "email": None,
            "posted_since": None,
            "additional_info": f"Raw model output: {raw_text[:150]}"
        }

    try:
        return GovTrackProfile(query=query, model_used=OPENROUTER_MODEL, **extracted).dict()
    except ValidationError as exc:
        print(f"   [warn] pydantic validation failed: {exc}")
        return GovTrackProfile(
            query=query,
            name=extracted.get("name", "Extraction failed"),
            role=extracted.get("role", query),
            cadre=extracted.get("cadre"),
            batch_year=extracted.get("batch_year"),
            district=extracted.get("district"),
            department=extracted.get("department"),
            party=extracted.get("party"),
            office_phone=extracted.get("office_phone"),
            email=extracted.get("email"),
            posted_since=extracted.get("posted_since"),
            additional_info=extracted.get("additional_info"),
            model_used=OPENROUTER_MODEL
        ).dict()



# TOOL 1 — fetch_authority
# Flow: Serper (Google search) → OpenRouter (AI extraction) → profile dict

async def fetch_authority(query: str) -> dict:
    search_query = f"{query} Tamil Nadu government official 2025"

    # Step 1 — Google search via Serper API
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={"q": search_query, "num": 6, "gl": "in", "hl": "en"}
        )
    search_data = resp.json()

    snippets = []
    sources  = []
    titles   = []

    # Pull answer box first (highest confidence)
    if search_data.get("answerBox", {}).get("snippet"):
        snippets.insert(0, search_data["answerBox"]["snippet"])
    if search_data.get("answerBox", {}).get("answer"):
        snippets.insert(0, search_data["answerBox"]["answer"])

    for r in search_data.get("organic", []):
        snippets.append(r.get("snippet", ""))
        sources.append(r.get("link", ""))
        titles.append(r.get("title", ""))

    # Step 2 — OpenRouter AI extracts structured profile from snippets
    extracted = await extract_with_openrouter(query, snippets[:5])

    # Step 3 — Build final enriched profile
    profile = {
        "query"        : query,
        **extracted,
        "sources"      : sources[:3],
        "source_titles": titles[:3],
        "raw_snippets" : snippets[:2],
        "model_used"   : OPENROUTER_MODEL,
        "fetched_at"   : datetime.now().isoformat(),
        "verified"     : True
    }
    return profile



# TOOL 2 — crud_profile  (CRUD on local data/profiles.json)

def crud_profile(action: str, profile: dict = None, query: str = "") -> dict:
    db = load_db()

    if action == "create":
        exists = next(
            (p for p in db["profiles"] if p.get("query") == profile.get("query")), None
        )
        if exists:
            exists.update(profile)
            save_db(db)
            return {"status": "updated", "total": len(db["profiles"])}
        db["profiles"].append(profile)
        save_db(db)
        return {"status": "created", "total": len(db["profiles"])}

    elif action == "read":
        if query:
            q = query.lower()
            matches = [
                p for p in db["profiles"]
                if q in p.get("query", "").lower()
                or q in (p.get("district") or "").lower()
                or q in (p.get("role") or "").lower()
                or q in (p.get("name") or "").lower()
            ]
            return {"profiles": matches, "count": len(matches)}
        return {"profiles": db["profiles"], "count": len(db["profiles"])}

    elif action == "update":
        for p in db["profiles"]:
            if p.get("query") == profile.get("query"):
                p.update(profile)
                save_db(db)
                return {"status": "updated"}
        return {"status": "not_found"}

    elif action == "delete":
        before = len(db["profiles"])
        db["profiles"] = [p for p in db["profiles"] if p.get("query") != query]
        save_db(db)
        return {"status": "deleted", "removed": before - len(db["profiles"])}

    return {"status": "unknown_action"}



# TOOL 3 — push_to_dashboard  (POST to bridge server → React dashboard)

async def push_to_dashboard(profiles: list, message: str = "") -> dict:
    payload = {
        "profiles" : profiles,
        "message"  : message,
        "pushed_at": datetime.now().isoformat()
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/push",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
        return {
            "status"   : "pushed",
            "dashboard": "http://localhost:3000",
            "count"    : len(profiles),
            "message"  : message
        }
    except Exception as e:
        return {
            "status": "dashboard_offline",
            "error" : str(e),
            "tip"   : "Make sure bridge.cjs is running: node dashboard/bridge.cjs"
        }



# MCP — Tool Definitions

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_authority",
            description=(
                "Search Google (Serper API) for a Tamil Nadu government authority, "
                "then use OpenRouter AI (Mistral) to extract a clean structured profile. "
                "Handles: Collector, SP, MLA, MP, Minister, CM, IAS/IPS officers. "
                "Always call this first, then crud_profile to save, then push_to_dashboard."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language query. Examples: "
                            "'Collector of Coimbatore', 'SP of Salem', "
                            "'Tamil Nadu Chief Minister', 'MLA of Coimbatore North', "
                            "'MP of Chennai South'"
                        )
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="crud_profile",
            description=(
                "Create, Read, Update, or Delete Tamil Nadu government authority "
                "profiles in local JSON storage (data/profiles.json). "
                "action must be one of: 'create' | 'read' | 'update' | 'delete'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "read", "update", "delete"]
                    },
                    "profile": {
                        "type": "object",
                        "description": "Full profile dict — required for create and update"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search/filter term for read, or query key for delete"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="push_to_dashboard",
            description=(
                "Send government authority profiles to the live React dashboard "
                "at http://localhost:3000. Dashboard auto-refreshes. "
                "Always call this last, after fetch and save."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profiles": {
                        "type": "array",
                        "description": "List of profile objects to display on the dashboard"
                    },
                    "message": {
                        "type": "string",
                        "description": "Status message shown in the dashboard header"
                    }
                },
                "required": ["profiles"]
            }
        )
    ]



# MCP — Tool Executor

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "fetch_authority":
        result = await fetch_authority(arguments["query"])
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    elif name == "crud_profile":
        result = crud_profile(
            action  = arguments["action"],
            profile = arguments.get("profile", {}),
            query   = arguments.get("query", "")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "push_to_dashboard":
        result = await push_to_dashboard(
            profiles = arguments["profiles"],
            message  = arguments.get("message", "")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]



# Entry point

async def main():
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


# --- Flask REST API for HTTP endpoints (for dashboard and external triggers) ---
from flask import Flask, request, jsonify
import threading

flask_app = Flask(__name__)

# Fetch ownership details (internet)
@flask_app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json()
    company = data.get("company")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    profile = loop.run_until_complete(fetch_authority(company))
    return jsonify(profile)

# CRUD operations
@flask_app.route("/api/crud", methods=["POST"])
def api_crud():
    data = request.get_json()
    action = data.get("action")
    profile = data.get("profile")
    query = data.get("query", "")
    result = crud_profile(action, profile, query)
    return jsonify(result)

# Push to dashboard
@flask_app.route("/api/push", methods=["POST"])
def api_push():
    data = request.get_json()
    profiles = data.get("profiles", [])
    message = data.get("message", "")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(push_to_dashboard(profiles, message))
    return jsonify(result)

# Utility: Get all profiles
@flask_app.route("/api/profiles", methods=["GET"])
def api_profiles():
    result = crud_profile("read")
    return jsonify(result)

# Utility: Health check
@flask_app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"})

# Run both MCP server and Flask REST API
def run_flask():
    flask_app.run(port=5001, debug=False)

if __name__ == "__main__":
    # Start Flask in a separate thread
    threading.Thread(target=run_flask, daemon=True).start()
    # Start MCP server (stdio)
    asyncio.run(main())