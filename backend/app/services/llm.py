from __future__ import annotations

import json
import re

import httpx

from app.config import settings


class LlmError(RuntimeError):
    pass


JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
HF_ROUTER = "https://router.huggingface.co/v1/chat/completions"
TOKEN_HELP = (
    "Создайте fine-grained токен с правом «Make calls to Inference Providers»: "
    "https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained "
    "Затем замените HF_TOKEN в .env и перезапустите: docker compose up -d backend"
)

SYSTEM_PROMPT = """Ты профессиональный трейдер российского рынка MOEX: акции TQBR, биржевые фонды (ETF/БПИФ) и драгоценные металлы (золото, серебро, платина, палладий).
ЗАПРЕЩЕНО писать что-либо кроме JSON. Не пиши «Let me analyze», не пиши план, не пиши markdown.
Весь разбор клади внутрь полей JSON.

Порядок мысли (внутри полей, не снаружи):
1) Разбери график по фактам из входа: структура (HH/HL vs LH/LL), тренд относительно SMA, ближайшие support/resistance, ATR/волатильность, объём, RSI, последняя свеча. Не выдумывай уровни, которых нет во входе.
2) Соотнеси этот разбор с новостями эмитента, мировым фоном и макро. Явно скажи, подтверждают они график, спорят с ним или картина смешанная.
3) Только после этого дай сценарий цены на ближайшие 5 торговых сессий. Это не инвестиционная рекомендация и не обещание сделки.

Не давай одну «точную целевую цену». Дай ожидаемое изменение в процентах от last_close, коридор и 5 точек траектории.
Не выходи за max_reasonable_move_pct из входа: это потолок правдоподобного хода за 5 сессий.
Формат ответа — один JSON-объект:
{
  "chart_analysis": "2-4 предложения: как читается график",
  "news_vs_chart": "confirm" | "contradict" | "mixed",
  "news_alignment": "как новости и макро соотносятся с графиком",
  "direction": "up" | "down" | "sideways",
  "confidence": число от 0 до 1,
  "expected_change_pct": число, ожидаемый ход close через 5 сессий в % к last_close,
  "range_low_pct": нижняя граница коридора в % (может быть отрицательной),
  "range_high_pct": верхняя граница коридора в %,
  "path": [
    {"t": 1, "change_pct": число},
    {"t": 2, "change_pct": число},
    {"t": 3, "change_pct": число},
    {"t": 4, "change_pct": число},
    {"t": 5, "change_pct": число}
  ],
  "thesis": "2-4 предложения: итог сценария",
  "news_factors": "как новости влияют",
  "macro_factors": "как макро/мир влияют",
  "risks": "что сломает сценарий"
}
path — накопленное изменение close относительно сегодняшнего last_close после 1..5 сессий.
t=5 должно быть близко к expected_change_pct.
range_low_pct <= expected_change_pct <= range_high_pct.
sideways — если ясного направления нет; тогда |expected_change_pct| небольшой, коридор шире.
"""


def _extract_json(text: str) -> dict:
    candidates: list[str] = []
    fenced = JSON_FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    greedy = JSON_OBJECT.search(text)
    if greedy:
        candidates.append(greedy.group(0))
    start = text.find("{")
    if start >= 0:
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(text[start:])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    for blob in candidates:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    snippet = re.sub(r"\s+", " ", text).strip()[:280]
    raise LlmError(f"Модель не вернула JSON{': ' + snippet if snippet else ''}")


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


def _as_float(value: object, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def parse_path(raw: object, horizon: int = 5) -> list[dict]:
    points: list[dict] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                t = int(_as_float(item.get("t"), index) or index)
                change = _as_float(item.get("change_pct") or item.get("pct") or item.get("y"))
            else:
                t = index
                change = _as_float(item)
            if change is None:
                continue
            points.append({"t": t, "change_pct": change})
    by_t = {int(p["t"]): float(p["change_pct"]) for p in points if 1 <= int(p["t"]) <= horizon}
    return [{"t": t, "change_pct": by_t[t]} for t in range(1, horizon + 1) if t in by_t]


def complete_analyst(user_prompt: str) -> tuple[dict, str]:
    token = settings.hf_token
    if not token:
        raise LlmError("Не задан HF_TOKEN. " + TOKEN_HELP)

    payload = {
        "model": _model_id(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": "{"},
        ],
        "max_tokens": 2200,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
        "extra_body": {
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
        },
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
        if response.status_code == 400:
            payload.pop("response_format", None)
            messages = payload.get("messages") or []
            if messages and messages[-1].get("role") == "assistant":
                payload["messages"] = messages[:-1]
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
        text = "\n".join(
            part for part in (message.get("content"), message.get("reasoning_content")) if part
        )
    except Exception as exc:  # noqa: BLE001
        raise LlmError(f"Пустой ответ модели: {exc}") from exc
    if not text:
        raise LlmError("Пустой ответ модели")
    if not text.lstrip().startswith("{"):
        text = "{" + text

    parsed = _extract_json(text)
    direction = str(parsed.get("direction", "sideways")).lower()
    if direction not in {"up", "down", "sideways"}:
        direction = "sideways"
    parsed["direction"] = direction
    alignment = str(parsed.get("news_vs_chart", "mixed")).lower()
    if alignment not in {"confirm", "contradict", "mixed"}:
        alignment = "mixed"
    parsed["news_vs_chart"] = alignment
    confidence = _as_float(parsed.get("confidence"), 0.5) or 0.5
    parsed["confidence"] = max(0.0, min(1.0, confidence))
    parsed["expected_change_pct"] = _as_float(parsed.get("expected_change_pct"))
    parsed["range_low_pct"] = _as_float(parsed.get("range_low_pct"))
    parsed["range_high_pct"] = _as_float(parsed.get("range_high_pct"))
    parsed["path"] = parse_path(parsed.get("path"), settings.forecast_horizon_days)
    parsed["chart_analysis"] = _as_text(parsed.get("chart_analysis"))
    parsed["news_alignment"] = _as_text(parsed.get("news_alignment"))
    parsed["thesis"] = _as_text(parsed.get("thesis")) or text[:1500]
    parsed["news_factors"] = _as_text(parsed.get("news_factors"))
    parsed["macro_factors"] = _as_text(parsed.get("macro_factors"))
    parsed["risks"] = _as_text(parsed.get("risks"))
    return parsed, text
