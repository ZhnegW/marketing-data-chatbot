from __future__ import annotations

import json
import os
from dotenv import load_dotenv
from typing import Optional, Tuple, Any, Dict, Literal

import pandas as pd
from openai import OpenAI
from pydantic import ValidationError, BaseModel

from schema import QuerySpec, PatchSpec, ALLOWED_FIELDS

load_dotenv()

def _df_context(df: pd.DataFrame) -> str:
    dtypes = {c: str(df[c].dtype) for c in df.columns}
    min_date = df["Date"].min()
    max_date = df["Date"].max()

    # Make sample JSON-safe (Timestamp -> string)
    sample_rows = df.head(3).copy()
    if "Date" in sample_rows.columns:
        sample_rows["Date"] = sample_rows["Date"].dt.strftime("%Y-%m-%d")

    sample = sample_rows.to_dict(orient="records")

    return (
        f"Columns & dtypes: {json.dumps(dtypes, ensure_ascii=False)}\n"
        f"Date coverage: {min_date.date()} ~ {max_date.date()}\n"
        f"Sample rows (first 3): {json.dumps(sample, ensure_ascii=False)}\n"
        f"Allowed fields: {sorted(list(ALLOWED_FIELDS))}\n"
    )


# 定义一个顶层模型，专门用于生成正确的 Schema 结构
class MarketingResponse(BaseModel):
    kind: Literal["query", "patch"]
    query_spec: Optional[QuerySpec] = None
    patch_spec: Optional[PatchSpec] = None

# 你的 _wrapper_json_schema 修改如下：

def _wrapper_json_schema() -> dict:
    # 1. 使用 Pydantic 生成原始 Schema
    # (假设你用了我之前推荐的 MarketingResponse Wrapper 类，或者你原来的写法)
    # 这里以你原来的写法为例，但建议用 Wrapper 类会更稳
    
    # 临时定义一个总包 Wrapper，让 Pydantic 处理 $ref 引用问题（这很重要！）
    class Wrapper(BaseModel):
        kind: str
        query_spec: Optional[QuerySpec] = None
        patch_spec: Optional[PatchSpec] = None

    raw_schema = Wrapper.model_json_schema()
    
    # 2. 清理不需要的顶层字段
    raw_schema.pop("title", None)

    # 3. 强力修正 Schema 以符合 Strict 模式
    final_schema = enforce_strict_constraints(raw_schema)

    return {
        "name": "marketing_query_or_patch",
        "strict": True,
        "schema": final_schema
    }



def _system_prompt(df: pd.DataFrame, last_spec: Optional[QuerySpec]) -> str:
    ctx = _df_context(df)

    last = ""
    if last_spec is not None:
        # 先把 Pydantic 模型转成 dict，再用 json 库转字符串
        last = f"\nPrevious QuerySpec (for follow-ups):\n{json.dumps(last_spec.model_dump(), ensure_ascii=False)}\n"

    return f"""
You are a data analyst assistant for a marketing performance dataset in a pandas DataFrame named `df`.
You do NOT have access to full raw data. You must reason only using schema/coverage/sample.

{ctx}
{last}

Your job:
- Convert the user's natural-language request into a structured spec.
- Output MUST be a JSON object that matches the provided JSON Schema.
- If the user asks a follow-up (e.g. "same but last quarter", "now only for Product=X"), return kind="patch" with PatchSpec.
- Otherwise return kind="query" with QuerySpec.

Important semantics (must follow):
- Relative time like last_quarter/last_month must be based on the dataset max Date (not today's date).
- Profit means SUM(Revenue) - SUM(Cost).
- If the user asks for a time period outside coverage (e.g. 2024 when max is 2023), still return a spec (Year=2024),
  and set output appropriately; execution layer will handle "no data". Do NOT fabricate numbers.
- For quarter type, the value MUST be in the format 'YYYY QN', e.g., '2023 Q2'.

Guidance:
- For "total revenue", use output="single_value", metrics=["Revenue"], group_by=[].
- For "top N ... by revenue", use group_by=["..."], sort=[{{"by":"Revenue","dir":"desc"}}], limit=N.
- For "trend by month", group_by=["Month"], output="trend".
- Use only allowed fields.

If kind is query, you MUST include query_spec and MUST omit patch_spec or set it to null.
If kind is patch, you MUST include patch_spec and MUST omit query_spec or set it to null.
""".strip()

def _call_openai_structured(messages, model: str) -> dict:
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found. Please check the .env file.")
        
    client = OpenAI(api_key=api_key)

    # 2. Retrieve the repaired schema
    schema_param = {"type": "json_schema", "json_schema": _wrapper_json_schema()}

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format=schema_param, 
        )
        content = resp.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        print(f"OpenAI API call failed: {e}")
        raise e

def parse_user_to_spec(
    df: pd.DataFrame,
    user_text: str,
    last_spec: Optional[QuerySpec],
    model: str = "gpt-4o",
) -> Tuple[str, QuerySpec | PatchSpec, dict]:
    """
    Returns:
      kind: "query" or "patch"
      spec: QuerySpec or PatchSpec (validated)
      raw: the parsed JSON dict (for debugging/logging)
    """
    messages = [
        {"role": "system", "content": _system_prompt(df, last_spec)},
        {"role": "user", "content": user_text},
    ]

    raw = _call_openai_structured(messages, model=model)

    try:
        kind = raw["kind"]
        if kind == "query":
            if "query_spec" not in raw or raw["query_spec"] is None:
                raise ValueError("kind=query but query_spec missing/null")
            return "query", QuerySpec(**raw["query_spec"]), raw

        # patch
        if "patch_spec" not in raw or raw["patch_spec"] is None:
            raise ValueError("kind=patch but patch_spec missing/null")
        return "patch", PatchSpec(**raw["patch_spec"]), raw

    except (KeyError, ValidationError) as e:
        # Retry once: ask model to correct output
        repair = {
            "role": "user",
            "content": f"""
Your previous JSON did not validate.

ERROR:
{str(e)}

Return ONLY a valid JSON object matching the schema.
""".strip(),
        }
        messages2 = messages + [repair]
        raw2 = _call_openai_structured(messages2, model=model)

        kind2 = raw2["kind"]
        if kind2 == "query":
            return "query", QuerySpec(**raw2["query_spec"]), raw2
        else:
            return "patch", PatchSpec(**raw2["patch_spec"]), raw2
        
def enforce_strict_constraints(schema: dict) -> dict:
    """
    Recursively process JSON Schema to meet the two core requirements of OpenAI Strict Mode:
    1. All object types must have additionalProperties: False
    2. Every field in properties must appear in the required list
    """
    if not isinstance(schema, dict):
        return schema

    if schema.get("type") == "object":
        # Requirement 1: Prohibit additional attributes
        schema["additionalProperties"] = False
        
        # Requirement 2: All fields are required
        if "properties" in schema:
            properties = schema["properties"]
            all_keys = list(properties.keys())
            
            # Ensure the required list contains all keys
            # If it doesn't exist, create a new one; if it does exist, perform a union operation
            current_required = set(schema.get("required", []))
            for key in all_keys:
                if key not in current_required:
                    # Note: For optional fields, the schema generated by Pydantic
                    # should already be in the format { “anyOf”: [..., “null”] },
                    # so we can safely set it as required, and the model will return null.
                    schema.setdefault("required", []).append(key)
            
            # Recursively process each property internally
            for key, value in properties.items():
                schema["properties"][key] = enforce_strict_constraints(value)

    # Recursive processing definitions / $defs
    for key in ["$defs", "definitions"]:
        if key in schema and isinstance(schema[key], dict):
            for def_name, def_schema in schema[key].items():
                schema[key][def_name] = enforce_strict_constraints(def_schema)

    # Recursively process array elements
    if "items" in schema:
        schema["items"] = enforce_strict_constraints(schema["items"])

    # Recursively Processing Compose Types (anyOf, allOf, oneOf)
    for key in ["anyOf", "allOf", "oneOf"]:
        if key in schema and isinstance(schema[key], list):
            schema[key] = [enforce_strict_constraints(item) for item in schema[key]]

    return schema

