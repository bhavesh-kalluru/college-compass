import os
import json
import logging
from dataclasses import dataclass
from typing import Type, Optional

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.schemas import CollegeCompassResponse

LOGGER = logging.getLogger("college_compass.openai")


class OpenAIRankingError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


@dataclass
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout_s: int = 60


class OpenAIClient:
    """
    Uses OpenAI Responses API with Pydantic parsing when possible.
    Falls back to JSON-mode parsing if needed.
    """

    def __init__(self, config: Optional[OpenAIConfig] = None):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key and config is None:
            raise OpenAIRankingError("OPENAI_API_KEY is not set.")
        model = os.getenv("OPENAI_MODEL", "") or (config.model if config else "gpt-4o-mini")
        self.config = config or OpenAIConfig(api_key=api_key, model=model)
        self.client = OpenAI(api_key=self.config.api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        retry=retry_if_exception_type(OpenAIRankingError),
    )
    def rank(self, prompt: str, response_model: Type[BaseModel] = CollegeCompassResponse) -> CollegeCompassResponse:
        try:
            resp = self.client.responses.parse(
                model=self.config.model,
                input=[
                    {"role": "system", "content": "Return only a JSON object matching the schema."},
                    {"role": "user", "content": prompt},
                ],
                text_format=response_model,
            )
            parsed = resp.output_parsed
            if parsed is None:
                raise OpenAIRankingError("OpenAI returned no structured output.")
            return parsed
        except Exception as e:
            LOGGER.warning("Structured parse failed, falling back. Reason=%s", str(e))

        try:
            cc = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "Return ONLY valid JSON. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            text = cc.choices[0].message.content or "{}"
            data = json.loads(text)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            raise OpenAIRankingError("OpenAI returned invalid JSON. Please retry.")
        except Exception as e:
            raise OpenAIRankingError(f"OpenAI request failed: {str(e)[:200]}")
