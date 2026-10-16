import os
from openai import OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"

def get_client() -> OpenAI:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is required to run live model calls.")
    return OpenAI(api_key=key, base_url=OPENROUTER_URL)

def complete(messages: list[dict[str, str]], models: list[str], *, response_format: dict | None = None, max_tokens: int = 900, temperature: float = 0.2) -> tuple[str, str]:
    client = get_client()
    failures = []
    for model in models:
        try:
            response = client.chat.completions.create(model=model, messages=messages, response_format=response_format, max_tokens=max_tokens, temperature=temperature)
            content = response.choices[0].message.content
            if content:
                return content, model
            failures.append(f"{model}: empty response")
        except Exception as error:  # Do not expose vendor details or secrets to callers.
            failures.append(f"{model}: {type(error).__name__}")
    raise RuntimeError("No configured model completed the request: " + "; ".join(failures))
