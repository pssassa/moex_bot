from __future__ import annotations

import json
import re

import httpx

from app.config import settings


class LlmError(RuntimeError):
    pass


JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
HF_ROUTER = "https://router.huggingface.co/v1/chat/completions"
TOKEN_HELP = (
    "Создайте fine-grained токен с правом «Make calls to Inference Providers»: "
    "https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained "
    "Затем замените HF_TOKEN в .env и перезапустите: docker compose up -d backend"
)

SYSTEM_PROMPT = """Ты аналитик российского фондового рынка.
Тебе дают факты: котировки, новости, макро. Не выдумывай цифры и события, которых нет во входе.
Не давай точную целевую цену. Оцени сценарий на ближайшие дни/недели.
Ответь ТОЛЬКО JSON без markdown со полями:
{
  "direction": "up" | "down" | "sideways",
  "confidence": число от 0 до 1,
  "thesis": "2-5 предложений на русском",
  "news_factors": "как новости влияют",
  "macro_factors": "как макро/мир влияют",
  "risks": "главные риски сценария"
}
direction: up — скорее рост, down — скорее снижение, sideways — без ясного направления.
"""


def _extract_json(text: str) -> dict:
    match = JSON_OBJECT.search(text)
    if not match:
        raise LlmError("Модель не вернула JSON")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LlmError(f"Некорректный JSON от модели: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmError("JSON модели не объект")
    return data


def _model_id() -> str:
    model = settings.hf_model
    if ":" not in model and settings.hf_provider:
        return f"{model}:{settings.hf_provider}"
    return model


def _auth_error(status: int, body: str) -> LlmError:
    if status in {401, 403}:
        return LlmError(
            f"Hugging Face отклонил токен (HTTP {status}). {TOKEN_HELP}"
        )
    return LlmError(f"Hugging Face недоступен: HTTP {status} {body[:400]}")


def complete_analyst(user_prompt: str) -> tuple[dict, str]:
    token = settings.hf_token
    if not token:
        raise LlmError("Не задан HF_TOKEN. " + TOKEN_HELP)

    payload = {
        "model": _model_id(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1200,
        "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
    }
    try:
        response = httpx.post(
            HF_ROUTER,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=httpx.Timeout(180.0, connect=30.0),
        )
    except Exception as exc:  # noqa: BLE001
        raise LlmError(f"Hugging Face недоступен: {exc}") from exc

    if response.status_code >= 400:
        raise _auth_error(response.status_code, response.text)

    data = response.json()
    try:
        message = data["choices"][0]["message"]
        text = message.get("content") or message.get("reasoning_content") or ""
    except Exception as exc:  # noqa: BLE001
        raise LlmError(f"Пустой ответ модели: {exc}") from exc
    if not text:
        raise LlmError("Пустой ответ модели")

    parsed = _extract_json(text)
    direction = str(parsed.get("direction", "sideways")).lower()
    if direction not in {"up", "down", "sideways"}:
        direction = "sideways"
    parsed["direction"] = direction
    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    parsed["confidence"] = max(0.0, min(1.0, confidence))
    parsed.setdefault("thesis", text[:1500])
    return parsed, text
