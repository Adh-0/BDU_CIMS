"""
llm_client.py — LLM provider abstraction with circuit breaker.
Supports Groq (cloud/dev) and Ollama (local/deployment).
"""

import logging
import time
from collections import deque
from typing import Generator

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open (too many failures)."""
    pass


class CircuitBreaker:
    """Simple circuit breaker: if N failures in T seconds, stop trying."""

    def __init__(self, failure_threshold: int = 3, recovery_time: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failures: deque = deque()
        self.is_open = False
        self.opened_at = 0.0

    def record_failure(self):
        now = time.time()
        self.failures.append(now)
        # Remove failures older than recovery_time
        while self.failures and (now - self.failures[0]) > self.recovery_time:
            self.failures.popleft()
        if len(self.failures) >= self.failure_threshold:
            self.is_open = True
            self.opened_at = now
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_threshold} failures"
            )

    def record_success(self):
        self.failures.clear()
        self.is_open = False

    def check(self):
        if self.is_open:
            # Check if recovery time has passed
            if (time.time() - self.opened_at) > self.recovery_time:
                logger.info("Circuit breaker: recovery time passed, allowing retry")
                self.is_open = False
            else:
                raise CircuitBreakerOpen(
                    "LLM service is temporarily unavailable. Please try again later."
                )


class LLMClient:
    """Unified LLM client supporting Groq and Ollama with circuit breaker.

    Usage:
        client = LLMClient(provider="groq", api_key="...", model="llama-3.3-70b-versatile")
        response = client.generate(messages=[...])
        # or for streaming:
        for token in client.generate(messages=[...], stream=True):
            print(token, end="")
    """

    def __init__(
        self,
        provider: str = "groq",
        api_key: str = "",
        model: str = "llama-3.3-70b-versatile",
        base_url: str = "http://localhost:11434",
        timeout: int = 30,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ):
        self.provider = provider.lower()
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._circuit = CircuitBreaker()

        if self.provider == "groq":
            from groq import Groq
            if not api_key:
                raise ValueError("GROQ_API_KEY is required when using groq provider")
            self._client = Groq(api_key=api_key, timeout=timeout)
            logger.info(f"LLM: Groq ({model})")

        elif self.provider == "ollama":
            import ollama as ollama_lib
            self._ollama = ollama_lib
            self._base_url = base_url
            logger.info(f"LLM: Ollama @ {base_url} ({model})")

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """Generate a response from the LLM.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            stream: If True, returns a generator yielding tokens.

        Returns:
            Full response text (str) or token generator.
        """
        self._circuit.check()

        try:
            if stream:
                return self._stream(messages)
            else:
                result = self._complete(messages)
                self._circuit.record_success()
                return result
        except CircuitBreakerOpen:
            raise
        except Exception as e:
            self._circuit.record_failure()
            logger.error(f"LLM error ({self.provider}): {e}")
            raise

    def _complete(self, messages: list[dict]) -> str:
        """Non-streaming completion."""
        if self.provider == "groq":
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return resp.choices[0].message.content or ""

        elif self.provider == "ollama":
            resp = self._ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
            return resp["message"]["content"] or ""

    def _stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Streaming completion — yields tokens one at a time."""
        try:
            if self.provider == "groq":
                stream = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

            elif self.provider == "ollama":
                stream = self._ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "num_predict": self.max_tokens,
                        "temperature": self.temperature,
                    },
                    stream=True,
                )
                for chunk in stream:
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content

            self._circuit.record_success()

        except Exception as e:
            self._circuit.record_failure()
            logger.error(f"LLM streaming error: {e}")
            raise
