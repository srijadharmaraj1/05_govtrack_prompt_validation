from typing import List


def build_qualified_extraction_prompt(query: str, snippets: List[str]) -> str:
    snippet_text = "\n".join(f"- {snippet}" for snippet in snippets if snippet and snippet.strip())
    return f"""
You are an expert government-information extraction assistant.

TASK:
Extract details about the government official referenced in the query and search snippets.

OUTPUT REQUIREMENTS:
1. Return ONLY a valid JSON object.
2. Do not return markdown.
3. Do not return explanations.
4. Do not invent facts.
5. Use null when information is unavailable.
6. Follow the schema exactly.

Query:
{query}

Search Snippets:
{snippet_text}

Schema:
{{
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
}}

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
- Use null for unknown values.
- Output only JSON.

Example:
{{
  "name": "John Doe",
  "role": "District Collector",
  "cadre": "IAS",
  "batch_year": 2014,
  "district": "Salem",
  "state": "Tamil Nadu",
  "department": null,
  "party": null,
  "office_phone": null,
  "email": null,
  "posted_since": null,
  "additional_info": null
}}
"""