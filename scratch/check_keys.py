"""Checks that the API keys in .env work. Prints model names, never the keys.

    python -m scratch.check_keys
"""
import os

import httpx
from dotenv import load_dotenv

from sandbag.config import ROOT
from sandbag.registry import load_registry

load_dotenv(ROOT / ".env")
WANTED = ("llama-3.1-405b", "llama-3.1-8b", "llama-4-maverick", "gpt-4o-mini")  # what to look for on OpenRouter


def check_anthropic() -> None:
    print("\n== Anthropic ==")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return print("No ANTHROPIC_API_KEY line in .env")
    reply = httpx.get("https://api.anthropic.com/v1/models?limit=100", timeout=30,
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
    if reply.status_code != 200:
        return print(f"FAILED ({reply.status_code}): {reply.json().get('error', {}).get('message', reply.text[:200])}")
    available = {model["id"] for model in reply.json()["data"]}
    print(f"Key works. {len(available)} models available.")
    for spec in load_registry().values():
        if spec.provider == "anthropic":
            print(f"  {spec.key:<18}{spec.model:<32}{'ok' if spec.model in available else 'NOT AVAILABLE to this key'}")
    print("  All Claude models this key can use:", ", ".join(sorted(available)))


def check_openrouter() -> None:
    print("\n== OpenRouter ==")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return print("No OPENROUTER_API_KEY line in .env")
    headers = {"Authorization": f"Bearer {key}"}
    reply = httpx.get("https://openrouter.ai/api/v1/key", headers=headers, timeout=30)
    if reply.status_code != 200:
        return print(f"FAILED ({reply.status_code}): {reply.text[:200]}")
    account = reply.json()["data"]
    print(f"Key works. Used so far: ${account.get('usage')}; limit: {account.get('limit') or 'none set'}")

    models = httpx.get("https://openrouter.ai/api/v1/models", timeout=30).json()["data"]
    for model in models:
        if not any(name in model["id"] for name in WANTED):
            continue
        hosts = "?"
        try:  # which companies host this model, and in what precision
            endpoints = httpx.get(f"https://openrouter.ai/api/v1/models/{model['id']}/endpoints", headers=headers,
                                  timeout=30).json()["data"]["endpoints"]
            hosts = ", ".join(f"{e.get('provider_name')} ({e.get('quantization') or 'unknown'})" for e in endpoints)
        except Exception:
            pass
        price = model.get("pricing", {})
        print(f"  {model['id']}\n      per million tokens: in ${float(price.get('prompt', 0)) * 1e6:.2f}, "
              f"out ${float(price.get('completion', 0)) * 1e6:.2f}\n      hosts: {hosts}")

    # One tiny real request, to confirm the key can actually spend.
    reply = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, timeout=60,
                       json={"model": "meta-llama/llama-3.1-8b-instruct", "max_tokens": 5,
                             "messages": [{"role": "user", "content": "Reply with the word: ready"}]})
    if reply.status_code == 200:
        print("  Test request to llama-3.1-8b-instruct:", repr(reply.json()["choices"][0]["message"]["content"]))
    else:
        print(f"  Test request FAILED ({reply.status_code}): {reply.text[:300]}")


if __name__ == "__main__":
    check_anthropic()
    check_openrouter()
