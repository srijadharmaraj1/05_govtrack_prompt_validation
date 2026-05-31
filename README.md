# GovTrack Tamil Nadu – Prompt Qualification Project

## Overview

GovTrack Tamil Nadu is an AI-powered agent that identifies and tracks Tamil Nadu government officials using web search, structured extraction, local persistence, and a live dashboard.

The project demonstrates how a basic prompt was upgraded into a qualified ChatGPT/Claude-style prompt that produces schema-compliant output suitable for automated validation.

---

## Basic Prompt

The initial prompt focused on tool execution and workflow orchestration.

```text
You have access to GovTrack tools. Please do the following:

1. Use fetch_authority to search for:
   - "Collector of Coimbatore"
   - "SP of Coimbatore"
   - "MLA of Coimbatore North"

2. Use crud_profile to save each result to local storage

3. Use crud_profile to read all saved profiles

4. Use push_to_dashboard to send all profiles to the dashboard
   with the message "Coimbatore District Officers — Live"

After this, I should see all 3 profile cards at localhost:3000
```

---

## Qualified Final Prompt

The extraction workflow was upgraded using a ChatGPT/Claude/Cursor-style prompt that enforces deterministic and testable output.

```text
You are ChatGPT / Claude / Cursor.

You must return ONLY a valid JSON object, with no markdown fences, no explanation, and no extra text.
Use null for any field that cannot be determined.
Use the schema exactly as specified.

Query: "{query}"

Search snippets:
{snippet_text}

Return exactly:

{
  "name": null,
  "role": null,
  "cadre": null,
  "batch_year": null,
  "district": null,
  "state": "Tamil Nadu",
  "department": null,
  "party": null,
  "office_phone": null,
  "email": null,
  "posted_since": null,
  "additional_info": null
}

Rules:
- state must always be "Tamil Nadu"
- role must be one of:
  District Collector,
  Superintendent of Police,
  MLA,
  MP,
  Cabinet Minister,
  Chief Minister,
  IAS Officer,
  IPS Officer
- Use null for unknown values
- Output only the JSON object, nothing else
```

---

## Prompt Qualification Features

The qualified prompt introduces:

* JSON-only responses
* Fixed output schema
* Explicit null handling
* Restricted role values
* Deterministic extraction behavior
* Compatibility with automated validation
* Reduced hallucination risk

---

## Output Validation

The extracted output is validated using Pydantic before being saved or displayed.

Validation is enforced through the `GovTrackProfile` schema.

Example fields:

```json
{
  "name": "Example Officer",
  "role": "District Collector",
  "cadre": "IAS",
  "district": "Salem",
  "state": "Tamil Nadu"
}
```

If the generated output does not match the schema, validation fails before persistence.

---

## Implementation Files

| File                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `prompt_helper.py`   | Builds the qualified extraction prompt               |
| `models.py`          | Defines the GovTrackProfile Pydantic schema          |
| `agent.py`           | Executes search, extraction, validation, and storage |
| `govtrack_server.py` | Dashboard integration and profile serving            |

---

## Running the Project

```bash
python agent.py --query "Collector of Salem"
```

Example:

```bash
python agent.py --query "Get all top officers of Coimbatore district"
```

---

## Demonstration

The demonstration video shows:

1. Prompt qualification approach
2. Agent execution
3. Government official extraction
4. Pydantic validation
5. Profile storage
6. Dashboard updates

---

## Technologies Used

* Python
* OpenRouter
* Serper Search API
* Pydantic
* FastAPI
* React Dashboard

---

## Repository

[Add your GitHub repository link here]

## Demo Video

[Add your YouTube video link here]
