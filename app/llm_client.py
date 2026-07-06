import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv


class LLMClientError(Exception):
    pass


def get_ollama_settings() -> tuple[str, str]:
    load_dotenv()

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

    return base_url, model


def get_llm_metadata() -> dict:
    load_dotenv()

    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()
    base_url, model = get_ollama_settings()

    return {
        "provider": provider,
        "base_url": base_url,
        "model": model
    }


def call_ollama_text(system_prompt: str, user_prompt: str) -> str:
    """
    Call local Ollama chat API.

    No API key needed.
    Ollama must be running locally.
    """
    base_url, model = get_ollama_settings()

    url = f"{base_url}/api/chat"

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "options": {
            "temperature": 0
        }
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_text = response.read().decode("utf-8")
            response_json = json.loads(response_text)

    except urllib.error.URLError as exc:
        raise LLMClientError(
            "Could not connect to Ollama. Make sure Ollama is running. "
            "Try: ollama serve"
        ) from exc

    except json.JSONDecodeError as exc:
        raise LLMClientError("Ollama returned invalid JSON.") from exc

    try:
        return response_json["message"]["content"]
    except KeyError as exc:
        raise LLMClientError(
            f"Unexpected Ollama response shape: {response_json}"
        ) from exc


def call_llm_text(system_prompt: str, user_prompt: str) -> str:
    """
    Provider wrapper.

    For now we only support Ollama.
    Later we can add Groq without changing planner/codegen logic.
    """
    load_dotenv()

    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()

    if provider == "ollama":
        return call_ollama_text(system_prompt, user_prompt)

    raise LLMClientError(
        f"Unsupported LLM_PROVIDER: {provider}. For now use LLM_PROVIDER=ollama."
    )


if __name__ == "__main__":
    system_prompt = "You are a JSON-only assistant."
    user_prompt = "Return exactly one JSON object with keys status and backend. Backend should be ollama."

    text = call_llm_text(system_prompt, user_prompt)

    print("LLM metadata:")
    print(json.dumps(get_llm_metadata(), indent=2))
    print("")
    print("LLM response:")
    print(text)
