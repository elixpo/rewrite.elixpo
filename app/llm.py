"""Pollinations API wrapper using OpenAI SDK."""

from openai import OpenAI

_client = None


def get_client(api_key: str = "dummy") -> OpenAI:
    """Get or create the Pollinations OpenAI-compatible client."""
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://gen.pollinations.ai/v1",
            api_key=api_key,
        )
    return _client


def chat(
    messages: list[dict],
    model: str = "openai",
    temperature: float = 1.0,
    seed: int = -1,
) -> str:
    """Send a chat completion request and return the response text."""
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        seed=seed,
    )
    return response.choices[0].message.content
