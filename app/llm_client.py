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
        with urllib.request.urlopen(request, timeout=int(os.environ.get("LLM_TIMEOUT_SECONDS", "300"))) as response:
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


def call_groq_text(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise LLMClientError("GROQ_API_KEY is not set.")

    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    timeout_seconds = int(os.environ.get("LLM_TIMEOUT_SECONDS", "240"))
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.2"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LLMClientError(f"Groq API HTTP error {exc.code}: {body}") from exc
    except Exception as exc:
        raise LLMClientError(f"Groq API call failed: {exc}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMClientError(f"Groq API response did not contain message content: {data}") from exc


def call_llm_text(system_prompt: str, user_prompt: str) -> str:
    provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()

    if provider == "ollama":
        return call_ollama_text(system_prompt, user_prompt)

    if provider == "groq":
        return call_groq_text(system_prompt, user_prompt)

    raise LLMClientError(f"Unsupported LLM_PROVIDER: {provider}")


