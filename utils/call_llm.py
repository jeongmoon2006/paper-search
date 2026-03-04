import os
from google import genai


_CACHED_MODEL: str | None = None


def _extract_generate_models(client: genai.Client) -> list[str]:
    models: list[str] = []
    for model in client.models.list():
        actions = getattr(model, "supported_actions", []) or []
        if "generateContent" in actions:
            name = getattr(model, "name", "")
            if isinstance(name, str) and name:
                models.append(name)
    return models


def _normalize_model_name(model_name: str) -> str:
    return model_name if model_name.startswith("models/") else f"models/{model_name}"


def _resolve_model(client: genai.Client) -> str:
    requested = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    try:
        available = _extract_generate_models(client)
    except Exception:
        return requested

    if not available:
        return requested

    requested_full = _normalize_model_name(requested)
    available_set = set(available)
    if requested in available_set:
        return requested
    if requested_full in available_set:
        return requested_full

    fallback_preferences = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
    ]
    for preferred in fallback_preferences:
        if preferred in available_set:
            return preferred

    return available[0]


# Learn more about calling the LLM: https://the-pocket.github.io/PocketFlow/utility_function/llm.html
def call_llm(prompt):
    global _CACHED_MODEL

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Set it in your environment before running."
        )

    client = genai.Client(api_key=api_key)
    try:
        if _CACHED_MODEL is None:
            _CACHED_MODEL = _resolve_model(client)

        r = client.models.generate_content(
            model=_CACHED_MODEL,
            contents=prompt,
        )
        return (r.text or "").strip()
    except Exception as exc:
        message = str(exc).lower()
        if "api key" in message or "authentication" in message or "permission" in message:
            raise RuntimeError(
                "LLM authentication failed. Check GEMINI_API_KEY."
            ) from exc
        if "quota" in message or "rate" in message or "resource exhausted" in message:
            raise RuntimeError(
                "LLM quota/rate limit reached. Check plan, billing, or retry later."
            ) from exc
        raise RuntimeError(f"LLM request failed: {exc.__class__.__name__}") from exc
    
if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    available_models = _extract_generate_models(client)
    print("Available text-generation models:")
    for model_name in available_models:
        print(f"- {model_name}")

    print("\nSelected model:", _resolve_model(client))
    prompt = "What is the meaning of life?"
    print("\nSample response:")
    print(call_llm(prompt))
