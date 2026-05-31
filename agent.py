"""
GovTrack Agent
Run modes:
  CLI:    python agent.py
  Bridge: python agent.py --query "Collector of Salem"
"""
import sys
import asyncio
import json
import os
import argparse
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pydantic import ValidationError

from models import GovTrackProfile
from prompt_helper import build_qualified_extraction_prompt

# Fix Windows terminal Unicode/emoji encoding issue
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).parent / ".env")
SERPER_API_KEY     = os.getenv("SERPER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")
DASHBOARD_URL      = "http://localhost:3001"
DATA_FILE          = Path(__file__).parent / "data" / "profiles.json"
DATA_FILE.parent.mkdir(exist_ok=True)
if not DATA_FILE.exists():
    DATA_FILE.write_text(json.dumps({"profiles": [], "last_updated": ""}, indent=2))

TN_DISTRICTS = [
    "Ariyalur","Chengalpattu","Chennai","Coimbatore","Cuddalore","Dharmapuri",
    "Dindigul","Erode","Kallakurichi","Kancheepuram","Kanniyakumari","Karur",
    "Krishnagiri","Madurai","Mayiladuthurai","Nagapattinam","Namakkal","Nilgiris",
    "Perambalur","Pudukkottai","Ramanathapuram","Ranipet","Salem","Sivaganga",
    "Tenkasi","Thanjavur","Theni","Thoothukudi","Tiruchirappalli","Tirunelveli",
    "Tirupathur","Tiruppur","Tiruvallur","Tiruvannamalai","Tiruvarur",
    "Vellore","Viluppuram","Virudhunagar"
]


async def fetch_authority(query: str) -> dict:
    print(f"\n[Tool 1] Searching: '{query}'")

    # Step 1 - Google search via Serper
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": f"{query} Tamil Nadu government official 2025", "num": 6, "gl": "in", "hl": "en"}
        )
    data = resp.json()

    snippets, sources, titles = [], [], []
    if data.get("answerBox", {}).get("snippet"):
        snippets.insert(0, data["answerBox"]["snippet"])
    if data.get("answerBox", {}).get("answer"):
        snippets.insert(0, data["answerBox"]["answer"])
    for r in data.get("organic", []):
        snippets.append(r.get("snippet", ""))
        sources.append(r.get("link", ""))
        titles.append(r.get("title", ""))
    print(f"   Found {len(snippets)} snippets from Google")

    # Step 2 - OpenRouter extracts structured data using a qualified ChatGPT/Claude prompt
    print(f"[OpenRouter] Extracting with {OPENROUTER_MODEL}...")
    prompt = build_qualified_extraction_prompt(query, snippets[:5])

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
                "temperature": 0.0,
                "max_tokens": 600
            }
        )

    api_data = resp.json()
    raw = api_data["choices"][0]["message"]["content"].strip()
    print(f"   [debug] model raw: {raw[:150]}")

    # Try to extract JSON with 3 strategies
    extracted = None

    # Strategy 1: direct parse
    try:
        extracted = json.loads(raw)
    except Exception:
        pass

    # Strategy 2: strip markdown fences
    if not extracted and "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                try:
                    extracted = json.loads(part)
                    break
                except Exception:
                    pass

    # Strategy 3: find { } block anywhere in text
    if not extracted:
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                extracted = json.loads(raw[start:end])
            except Exception:
                pass

    # Fallback
    if not extracted:
        print(f"   [warn] Could not parse JSON. Full raw: {raw}")
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
            "additional_info": raw[:200]
        }

    try:
        profile = GovTrackProfile(
            query=query,
            model_used=OPENROUTER_MODEL,
            **extracted
        ).dict()
    except ValidationError as exc:
        print(f"   [warn] pydantic validation failed: {exc}")
        profile = GovTrackProfile(
            query=query,
            name=extracted.get("name") or "Extraction failed",
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
            sources=sources[:3],
            source_titles=titles[:3],
            raw_snippets=snippets[:2],
            model_used=OPENROUTER_MODEL
        ).dict()

    profile.update({
        "sources": sources[:3],
        "source_titles": titles[:3],
        "raw_snippets": snippets[:2],
        "model_used": OPENROUTER_MODEL,
        "fetched_at": datetime.now().isoformat(),
        "verified": True,
        "bookmarked": False,
        "flagged": False,
        "note": ""
    })
    print(f"   OK: {profile.get('name')} -- {profile.get('role')}")
    return profile


def crud_profile(action, profile=None, query=""):
    db = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if action == "create":
        exists = next((p for p in db["profiles"] if p.get("query") == profile.get("query")), None)
        if exists:
            profile["note"]       = exists.get("note", "")
            profile["bookmarked"] = exists.get("bookmarked", False)
            profile["flagged"]    = False
            exists.update(profile)
        else:
            db["profiles"].append(profile)
        db["last_updated"] = datetime.now().isoformat()
        DATA_FILE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Tool 2] Saved '{profile.get('name')}' (total: {len(db['profiles'])})")
    return {"status": "ok"}


async def push_to_dashboard(profiles, message=""):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/push",
                json={"profiles": profiles, "message": message, "pushed_at": datetime.now().isoformat()},
                headers={"Content-Type": "application/json"}
            )
        print(f"[Tool 3] Pushed {len(profiles)} profiles to dashboard")
    except Exception as e:
        print(f"[warn] Bridge offline: {e}")


def build_queries(prompt):
    pl = prompt.lower()
    queries = []
    district = next((d for d in TN_DISTRICTS if d.lower() in pl), None)

    if "chief minister" in pl or " cm " in pl or pl.startswith("cm"):
        queries.append("Tamil Nadu Chief Minister 2025")
    if district:
        fetch_all = any(x in pl for x in ["all", "officers", "top"])
        if fetch_all or "collector" in pl:
            queries.append(f"Collector of {district} district Tamil Nadu")
        if fetch_all or any(x in pl for x in ["sp ", "police", "superintendent"]):
            queries.append(f"Superintendent of Police SP {district} Tamil Nadu")
        if fetch_all or "mla" in pl:
            queries.append(f"MLA {district} Tamil Nadu 2021")
        if "mp" in pl or "parliament" in pl:
            queries.append(f"MP Member of Parliament {district} Tamil Nadu")

    return queries if queries else [prompt]


async def run_agent(prompt):
    print(f"\n{'='*60}\nGOVTRACK AGENT -- {prompt}\n{'='*60}")
    queries = build_queries(prompt)
    print(f"   Queries: {queries}")

    profiles = []
    for q in queries:
        profiles.append(await fetch_authority(q))
        await asyncio.sleep(0.5)

    for p in profiles:
        crud_profile("create", profile=p)

    district = next((d for d in TN_DISTRICTS if d.lower() in prompt.lower()), "Tamil Nadu")
    msg = f"{district} Officers -- {datetime.now().strftime('%d %b %Y %I:%M %p')}"
    await push_to_dashboard(profiles, msg)

    print(f"\nDONE! Open http://localhost:3000\n{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, default=None)
    args = parser.parse_args()

    if args.query:
        await run_agent(args.query)
    else:
        print("\nGovTrack Tamil Nadu -- AI Agent")
        print("-" * 40)
        print("Examples:")
        print("  Get all top officers of Coimbatore district")
        print("  Who is the Collector of Salem")
        print("  Tamil Nadu Chief Minister")
        print("-" * 40)
        prompt = input("\nEnter your query: ").strip() or "Get all top officers of Coimbatore district"
        await run_agent(prompt)


if __name__ == "__main__":
    asyncio.run(main())