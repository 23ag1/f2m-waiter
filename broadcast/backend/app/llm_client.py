"""
LLM dispatcher. Поддерживает DeepSeek и Bothub (OpenAI-совместимый формат).
"""

import os
import time
import requests
from typing import Optional


BOTHUB_API_URL = os.getenv(
    "BOTHUB_API_URL",
    "https://bothub.chat/api/v2/openai/v1/chat/completions"
)
BOTHUB_API_KEY = os.getenv("BOTHUB_API_KEY", "")
BOTHUB_MODEL = os.getenv("BOTHUB_MODEL", "gpt-4o-mini")

DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions"
)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _safe_resp_json(resp):
    try:
        return resp.json()
    except Exception:
        raise ValueError("Ответ API не является валидным JSON")


def _extract_content_from_openai_style(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise ValueError(f"Не удалось извлечь content из ответа: {e}")


def call_llm_chat(
    model_provider: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 45,
    retries: int = 2,
    backoff: float = 1.5,
    response_format: Optional[str] = None,
    debug: bool = False,
) -> str:
    """
    Универсальный вызов LLM в формате chat.completions.

    Поддерживаемые провайдеры: 'deepseek', 'bothub'.
    """
    if model_provider not in ("bothub", "deepseek"):
        raise ValueError("model_provider должен быть 'bothub' или 'deepseek'")

    if model_provider == "bothub":
        if not BOTHUB_API_KEY:
            raise RuntimeError("Не задан BOTHUB_API_KEY")
        url = BOTHUB_API_URL
        headers = {"Authorization": f"Bearer {BOTHUB_API_KEY}"}
        model = BOTHUB_MODEL
    else:
        if not DEEPSEEK_API_KEY:
            raise RuntimeError("Не задан DEEPSEEK_API_KEY")
        url = DEEPSEEK_API_URL
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        model = DEEPSEEK_MODEL

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
    }
    if response_format:
        body["response_format"] = {"type": response_format}

    last_err = None
    for attempt in range(retries + 1):
        try:
            if attempt > 0 and debug:
                print(f"[INFO] Повторная попытка {attempt + 1}/{retries + 1}")

            resp = requests.post(url, headers=headers, json=body, timeout=timeout)

            if debug:
                print(f"[DEBUG] HTTP {resp.status_code}")
                print(f"[DEBUG] body peek: {(resp.text or '')[:300]}")

            if not resp.ok:
                raise RuntimeError(f"HTTP {resp.status_code}: {(resp.text or '')[:300]}")

            data = _safe_resp_json(resp)
            return _extract_content_from_openai_style(data)

        except Exception as e:
            last_err = e
            if attempt < retries:
                wait = backoff ** attempt
                if debug:
                    print(f"[WARN] LLM ошибка: {e}; ждём {wait:.1f}с")
                time.sleep(wait)
            else:
                raise RuntimeError(f"LLM вызов не удался: {e}")

    raise RuntimeError(f"LLM ошибка: {last_err}")
