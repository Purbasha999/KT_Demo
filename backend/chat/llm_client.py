import httpx
from core.config import settings

async def _call(prompt: str, max_tokens: int, response_type: str) -> str:
    payload = {
        "system_prompt": "You are a helpful data assistant.",
        "user_prompt":   prompt,
        "model":         settings.LLM_MODEL,
        "temperature":   0,
        "max_tokens":    max_tokens,
        "response_type": response_type,
    }
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Token {settings.LLM_API_TOKEN}",
    }
    timeout = httpx.Timeout(
        connect=10.0,   # 10s to establish connection
        read=60.0,      # 60s to wait for response
        write=10.0,
        pool=10.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            settings.LLM_API_URL, json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()

    content = data.get("content", "")
    if not content:
        raise ValueError(f"Empty response from LLM service: {data}")
    return content.strip()


async def generate_sql(prompt: str) -> str:
    return await _call(prompt, max_tokens=500, response_type="text")


async def generate_mongo_query(prompt: str) -> str:
    return await _call(prompt, max_tokens=500, response_type="json_object")


async def format_response(prompt: str) -> str:
    return await _call(prompt, max_tokens=1000, response_type="text")
