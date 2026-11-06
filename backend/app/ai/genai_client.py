"""
Thin adapter over Google's `google-genai` SDK (the supported successor of the retired
`google-generativeai` package). Every Gemini call in the backend goes through these two functions,
so the SDK is used in one place and is easy to mock in tests.

Both functions are blocking; callers run them with `asyncio.to_thread`.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Sequence, Union

# One client per API key (clients hold an HTTP connection pool and are thread-safe)
_clients: Dict[str, Any] = {}
_lock = threading.Lock()

REQUEST_TIMEOUT_MS = 120_000


def _model_id(model: str) -> str:
    return (model or "").strip().replace("models/", "")


def get_client(api_key: str):
    from google import genai
    from google.genai import types

    with _lock:
        client = _clients.get(api_key)
        if client is None:
            # No retries inside the SDK: the AI gateway retries once, then fails over to the
            # secondary provider, and a 429 must reach it quickly to start the cooldown
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)
                ),
            )
            _clients[api_key] = client
        return client


def generate_content(
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    json_output: bool = False,
    images: Optional[Sequence[bytes]] = None,
    image_mime_type: str = "image/png",
) -> str:
    """Generates text (or JSON text when `json_output`) and returns it ('' if the model gave none)."""
    from google.genai import types

    config_fields: Dict[str, Any] = {}
    if system_instruction:
        config_fields["system_instruction"] = system_instruction
    if temperature is not None:
        config_fields["temperature"] = float(temperature)
    if max_output_tokens is not None:
        config_fields["max_output_tokens"] = int(max_output_tokens)
    if json_output:
        config_fields["response_mime_type"] = "application/json"

    contents: Union[str, List[Any]] = prompt
    if images:
        contents = [prompt] + [types.Part.from_bytes(data=img, mime_type=image_mime_type) for img in images]

    response = get_client(api_key).models.generate_content(
        model=_model_id(model),
        contents=contents,
        config=types.GenerateContentConfig(**config_fields) if config_fields else None,
    )
    return (getattr(response, "text", None) or "").strip()


def embed_content(
    model: str,
    content: Union[str, Sequence[str]],
    task_type: str,
    output_dimensionality: Optional[int] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Embeds one text or a batch. Returns {"embedding": vector} for one text and
    {"embedding": [vector, ...]} for a batch (the shape the callers were written for)."""
    from google.genai import types

    single = isinstance(content, str)
    config = types.EmbedContentConfig(
        task_type=task_type.upper(),
        output_dimensionality=output_dimensionality,
    )
    result = get_client(api_key or "").models.embed_content(
        model=_model_id(model),
        contents=[content] if single else list(content),
        config=config,
    )
    vectors = [list(e.values or []) for e in (result.embeddings or [])]
    return {"embedding": vectors[0] if single and vectors else vectors}
