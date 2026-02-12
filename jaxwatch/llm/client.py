#!/usr/bin/env python3
"""
JaxWatch Unified LLM Client
Single interface for all LLM operations across the project.
"""

import json
import logging
from typing import Any, Optional
from pathlib import Path

from jaxwatch.config.manager import get_config, JaxWatchConfig

logger = logging.getLogger("jaxwatch.llm")

# Global client instance
_global_client: Optional['LLMClient'] = None


class LLMClient:
    """MLX-powered LLM client for Apple Silicon optimization.

    Supports:
    - MLX local inference only
    - JSON mode for structured responses
    - Configurable max_tokens
    """

    def __init__(self, config: Optional[JaxWatchConfig] = None):
        self.config = config or get_config()
        self._model_name = self.config.llm.model
        self._model = None
        self._tokenizer = None
        self._load_mlx_model()

    def _load_mlx_model(self):
        """Load MLX model - MLX handles caching automatically."""
        try:
            from mlx_lm import load
        except ImportError as e:
            logger.error("MLX not available. Please install MLX dependencies: pip install mlx mlx-lm transformers torch")
            raise ImportError("MLX dependencies required") from e

        # MLX automatically handles caching - just use the model identifier directly
        logger.info(f"Loading MLX model: {self._model_name}")
        try:
            self._model, self._tokenizer = load(self._model_name)
            logger.info(f"Successfully loaded MLX model: {self._model_name}")
        except Exception as e:
            logger.error(f"Failed to load MLX model {self._model_name}: {e}")
            raise

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def api_url(self) -> str:
        return "mlx://local"

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
            temperature: Sampling temperature (ignored in MLX, kept for API compatibility)
            timeout: Request timeout (ignored in MLX, kept for API compatibility)

        Returns:
            Response text, or None if request failed
        """
        try:
            from mlx_lm import generate

            messages = []
            if json_mode:
                messages.append({
                    "role": "system",
                    "content": "You are a JSON extraction bot. Always respond with valid JSON only, no other text."
                })
            messages.append({"role": "user", "content": prompt})

            formatted_prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            response = generate(
                self._model,
                self._tokenizer,
                prompt=formatted_prompt,
                max_tokens=self.config.llm.mlx_options.get('max_tokens', 2048),
                verbose=False
            )
            return response

        except Exception as e:
            logger.error(f"MLX chat request failed: {e}")
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
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks or other formats
            import re

            # Try to find JSON within ```json or ``` blocks
            json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            match = re.search(json_pattern, content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

            # Try to find JSON object directly
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            match = re.search(json_pattern, content)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.error(f"Failed to parse LLM response as JSON")
            logger.debug(f"Raw content: {content[:500]}...")
            return None

    def is_available(self) -> bool:
        """Check if the MLX model is loaded and available."""
        return self._model is not None and self._tokenizer is not None


def get_llm_client(config: Optional[JaxWatchConfig] = None) -> LLMClient:
    """Get global LLM client instance."""
    global _global_client
    if _global_client is None:
        _global_client = LLMClient(config)
    return _global_client
