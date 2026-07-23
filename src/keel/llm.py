"""LLM providers for the evolution brain — Ollama (local), Claude, or Gemini.

Preference order is **local first**: Ollama keeps your research private and free;
Claude and Gemini are used only if their API keys are in your environment. All
three are stdlib-only HTTP (no SDK dependency).

The LLM's job in Keel is narrow and safe: propose *candidate* strategy variants
(see `keel.advisor`). It never sees your keys beyond what you set, never places
an order, and never has the final say — every proposal it makes is judged by the
same statistics as everything else. It is a brainstorming partner behind a locked
door, not an autonomous trader.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    name: str

    def complete(self, prompt: str, system: str = "") -> str: ...


def _post(url: str, body: dict, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 http(s)
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:  # pragma: no cover - network
        raise LLMError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
    except urllib.error.URLError as e:  # pragma: no cover - network
        raise LLMError(f"cannot reach {url}: {e.reason}") from e


class OllamaProvider:
    def __init__(self, model: str):
        self.model = model
        self.name = f"ollama:{model}"

    @staticmethod
    def available() -> bool:
        try:
            with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:  # noqa: S310
                return r.status == 200
        except Exception:
            return False

    def complete(self, prompt: str, system: str = "") -> str:
        body = {"model": self.model, "prompt": prompt, "system": system, "stream": False}
        out = _post(f"{OLLAMA_URL}/api/generate", body, {"Content-Type": "application/json"})
        return out.get("response", "")


class ClaudeProvider:
    def __init__(self, model: str | None = None):
        self.key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        self.model = model or os.getenv("KEEL_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.name = f"claude:{self.model}"

    def available(self) -> bool:
        return bool(self.key)

    def complete(self, prompt: str, system: str = "") -> str:
        body = {
            "model": self.model,
            "max_tokens": 1500,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        out = _post("https://api.anthropic.com/v1/messages", body, headers)
        parts = out.get("content", [])
        return "".join(p.get("text", "") for p in parts)


class GeminiProvider:
    def __init__(self, model: str | None = None):
        self.key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("KEEL_GEMINI_MODEL", "gemini-2.0-flash")
        self.name = f"gemini:{self.model}"

    def available(self) -> bool:
        return bool(self.key)

    def complete(self, prompt: str, system: str = "") -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.key}"
        )
        text = (system + "\n\n" + prompt) if system else prompt
        body = {"contents": [{"parts": [{"text": text}]}]}
        out = _post(url, body, {"Content-Type": "application/json"})
        try:
            return out["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return ""


def total_ram_gb() -> float:
    """Best-effort physical RAM in GB (for model sizing). Falls back to ~16."""
    try:
        import psutil

        return psutil.virtual_memory().total / 1e9
    except Exception:
        pass
    try:  # Linux
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / 1e6
    except Exception:
        pass
    try:  # Windows
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [
                ("l", ctypes.c_ulong),
                ("m", ctypes.c_uint),
                ("t", ctypes.c_ulonglong),
                ("a", ctypes.c_ulonglong),
                ("tp", ctypes.c_ulonglong),
                ("ap", ctypes.c_ulonglong),
                ("tv", ctypes.c_ulonglong),
                ("av", ctypes.c_ulonglong),
                ("ae", ctypes.c_ulonglong),
            ]

        s = MS()
        s.l = ctypes.sizeof(s)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
        return s.t / 1e9
    except Exception:
        return 16.0


def recommend_ollama_model(ram_gb: float | None = None) -> str:
    """Pick a Qwen3 model (the 2026 local agentic-reasoning pick) sized to RAM."""
    ram = ram_gb if ram_gb is not None else total_ram_gb()
    if ram < 8:
        return "qwen3:4b"
    if ram < 16:
        return "qwen3:8b"
    if ram < 32:
        return "qwen3:14b"
    return "qwen3:30b"


def pick_provider(prefer: str | None = None):
    """Return an available provider, local-first. `prefer` in {ollama,claude,gemini}."""
    order = [prefer] if prefer else []
    order += ["ollama", "claude", "gemini"]
    for choice in order:
        if choice == "ollama" and OllamaProvider.available():
            return OllamaProvider(recommend_ollama_model())
        if choice == "claude" and ClaudeProvider().available():
            return ClaudeProvider()
        if choice == "gemini" and GeminiProvider().available():
            return GeminiProvider()
    return None
