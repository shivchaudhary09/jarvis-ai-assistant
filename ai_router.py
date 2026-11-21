"""Routes JARVIS chat requests to Groq or a local Ollama model."""

import os
from typing import Any, Dict, List, Optional

from groq import Groq
from ollama import Client as OllamaClient


class AIRouter:
    """Use Groq by default, with Ollama available as the local provider."""

    def __init__(self, system_prompt: str, history: Optional[List[Dict[str, str]]] = None):
        self.system_prompt = system_prompt
        self.history = self._normalise_history(history or [])
        self.provider = os.getenv("AI_PROVIDER", "groq").lower()
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.ollama_client = OllamaClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))

        api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=api_key) if api_key else None
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    @staticmethod
    def _normalise_history(history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Keep only the provider-neutral history format used by this project."""
        normalised = []
        for message in history:
            role = message.get("role")
            content = message.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                normalised.append({"role": role, "content": content})
        return normalised

    def set_system_prompt(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt

    def set_provider(self, provider: str) -> None:
        """Switch the provider for this running JARVIS session."""
        provider = provider.lower()
        if provider not in {"auto", "ollama", "groq"}:
            raise ValueError("Provider must be 'auto', 'ollama', or 'groq'.")
        if provider == "groq" and not self.groq_client:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        self.provider = provider

    def send_message(self, user_input: str) -> str:
        """Return a response and add the completed turn to local chat history."""
        messages = [{"role": "system", "content": self.system_prompt}, *self.history]
        messages.append({"role": "user", "content": user_input})

        if self.provider == "ollama":
            reply = self._send_ollama(messages)
        elif self.provider == "groq":
            reply = self._send_groq(messages)
        elif self.provider == "auto":
            try:
                reply = self._send_groq(messages)
            except Exception as groq_error:
                if not self._is_quota_error(groq_error):
                    raise
                try:
                    reply = self._send_ollama(messages)
                except Exception as ollama_error:
                    raise RuntimeError(
                        "Groq rate limit exceeded and local Ollama is unavailable. "
                        "Please run `ollama serve` and pull your model: "
                        f"`ollama pull {self.ollama_model}`."
                    ) from ollama_error

                # Do not keep making quota-exhausted cloud requests in this session.
                self.provider = "ollama"
                print("[JARVIS: Groq quota exceeded — switched to local Ollama.]")
        else:
            raise ValueError("AI_PROVIDER must be 'auto', 'ollama', or 'groq'.")

        self.history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": reply},
        ])
        return reply

    def extract_json(self, prompt: str) -> str:
        """Extract a JSON command using whichever provider is currently active."""
        if self.provider == "ollama":
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )
            return response["message"]["content"].strip()

        if self.provider == "groq":
            return self._extract_json_groq(prompt)

        # In auto mode use Groq first, then Ollama on quota exhaustion.
        try:
            return self._extract_json_groq(prompt)
        except Exception as groq_error:
            if not self._is_quota_error(groq_error):
                raise
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )
            self.provider = "ollama"
            print("[JARVIS: Automation ke liye Groq limit khatam — Ollama use kar raha hoon.]")
            return response["message"]["content"].strip()

    def _extract_json_groq(self, prompt: str) -> str:
        if not self.groq_client:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        response = self.groq_client.chat.completions.create(
            model=self.groq_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _is_quota_error(error: Exception) -> bool:
        """Identify Groq rate-limit and quota-exhaustion responses."""
        status_code = getattr(error, "code", None)
        if status_code == 429:
            return True
        error_text = str(error).lower()
        quota_markers = ("429", "resource exhausted", "resource_exhausted", "quota", "rate limit")
        return any(marker in error_text for marker in quota_markers)

    def _send_ollama(self, messages: List[Dict[str, str]]) -> str:
        response = self.ollama_client.chat(model=self.ollama_model, messages=messages)
        return response["message"]["content"].strip()

    def _send_groq(self, messages: List[Dict[str, str]]) -> str:
        if not self.groq_client:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        response = self.groq_client.chat.completions.create(
            model=self.groq_model,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
