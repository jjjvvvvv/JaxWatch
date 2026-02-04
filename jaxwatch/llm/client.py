#!/usr/bin/env python3
"""
JaxWatch Unified LLM Client
Single interface for all LLM operations across the project.
"""

import json
import logging
from typing import Any, Optional

import requests

from jaxwatch.config.manager import get_config, JaxWatchConfig

logger = logging.getLogger("jaxwatch.llm")

# Global client instance
_global_client: Optional['LLMClient'] = None


class LLMClient:
    """Unified LLM client for JaxWatch.

    Supports:
    - Ollama (local, default)
    - JSON mode for structured responses
    - Configurable temperature and timeout
    """

    def __init__(self, config: Optional[JaxWatchConfig] = None):
        self.config = config or get_config()
        self._api_url = self.config.llm.api_url
        self._model = self.config.llm.model
        self._api_key = self.config.llm.api_key

    @property
    def model(self) -> str:
        return self._model

    @property
    def api_url(self) -> str:
        return self._api_url

    def chat(
        self,
        prompt: str,
        json_mode: bool = False,
        temperature: float = 0.0,
        timeout: int = 120
    ) -> Optional[str]:
        """Send a chat message to the LLM and return the response.

        Args:
            prompt: The user prompt to send
            json_mode: If True, request JSON-formatted response
            temperature: Sampling temperature (0.0 = deterministic)
            timeout: Request timeout in seconds

        Returns:
            Response text, or None if request failed
        """
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature},
        }

        if json_mode:
            payload["format"] = "json"

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            resp = requests.post(
                self._api_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            resp.raise_for_status()

            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content

        except requests.exceptions.Timeout:
            logger.error(f"LLM request timed out after {timeout}s")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            return None

    def chat_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        timeout: int = 120
    ) -> Optional[Any]:
        """Send a chat message and parse the response as JSON.

        Args:
            prompt: The user prompt to send
            temperature: Sampling temperature (0.0 = deterministic)
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON object, or None if request/parsing failed
        """
        content = self.chat(
            prompt=prompt,
            json_mode=True,
            temperature=temperature,
            timeout=timeout
        )

        if content is None:
            return None

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw content: {content[:500]}...")
            return None

    def is_available(self) -> bool:
        """Check if the LLM service is available."""
        try:
            # Simple health check - try a minimal request
            resp = requests.get(
                self._api_url.replace("/api/chat", "/api/tags"),
                timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False


def get_llm_client(config: Optional[JaxWatchConfig] = None) -> LLMClient:
    """Get global LLM client instance."""
    global _global_client
    if _global_client is None or config is not None:
        _global_client = LLMClient(config)
    return _global_client
