"""
This module contains functions to interact with the models.
"""

import json
import os
from typing import List, Optional, Tuple

import litellm

DEFAULT_SUMMARIZE_INSTRUCTION = "Summarize the given text without changing the language of it."  # pylint: disable=line-too-long
DEFAULT_TRANSLATE_INSTRUCTION = "Translate the given text from {source_lang} to {target_lang}."  # pylint: disable=line-too-long


class ContextWindowExceededError(Exception):
  pass


class Model:

  def __init__(
      self,
      name: str,
      provider: str = None,
      api_key: str = None,
      api_base: str = None,
      summarize_instruction: str = None,
      translate_instruction: str = None,
  ):
    self.name = name
    self.provider = provider
    self.api_key = api_key
    self.api_base = api_base
    self.summarize_instruction = summarize_instruction or DEFAULT_SUMMARIZE_INSTRUCTION  # pylint: disable=line-too-long
    self.translate_instruction = translate_instruction or DEFAULT_TRANSLATE_INSTRUCTION  # pylint: disable=line-too-long

  # Returns the parsed result or raw response, and whether parsing succeeded.
  def completion(self,
                 instruction: str,
                 prompt: str,
                 max_tokens: Optional[float] = None,
                 max_retries: int = 2) -> Tuple[str, bool]:
    messages = [{
        "role":
            "system",
        "content":
            instruction + """
Output following this JSON format without using code blocks:
{"result": "your result here"}"""
    }, {
        "role": "user",
        "content": prompt
    }]

    for attempt in range(max_retries + 1):
      try:
        response = litellm.completion(model=self.provider + "/" +
                                      self.name if self.provider else self.name,
                                      api_key=self.api_key,
                                      api_base=self.api_base,
                                      messages=messages,
                                      max_tokens=max_tokens,
                                      **self._get_completion_kwargs())

        json_response = response.choices[0].message.content
        parsed_json = json.loads(json_response)
        return parsed_json["result"], True

      except litellm.ContextWindowExceededError as e:
        raise ContextWindowExceededError() from e
      except json.JSONDecodeError:
        if attempt == max_retries:
          return json_response, False

  def _get_completion_kwargs(self):
    return {
        # Ref: https://litellm.vercel.app/docs/completion/input#optional-fields # pylint: disable=line-too-long
        "response_format": {
            "type": "json_object"
        }
    }


class AnthropicModel(Model):

  def completion(self,
                 instruction: str,
                 prompt: str,
                 max_tokens: Optional[float] = None,
                 max_retries: int = 2) -> Tuple[str, bool]:
    # Ref: https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency#prefill-claudes-response # pylint: disable=line-too-long
    prefix = "<result>"
    suffix = "</result>"
    messages = [{
        "role":
            "user",
        "content":
            f"""{instruction}
Output following this format:
{prefix}...{suffix}
Text:
{prompt}"""
    }, {
        "role": "assistant",
        "content": prefix
    }]

    for attempt in range(max_retries + 1):
      try:
        response = litellm.completion(
            model=self.provider + "/" +
            self.name if self.provider else self.name,
            api_key=self.api_key,
            api_base=self.api_base,
            messages=messages,
            max_tokens=max_tokens,
        )

      except litellm.ContextWindowExceededError as e:
        raise ContextWindowExceededError() from e

      result = response.choices[0].message.content
      if result.endswith(suffix):
        return result.removesuffix(suffix).strip(), True

      if attempt == max_retries:
        return result, False


class VertexModel(Model):

  def __init__(self, name: str, vertex_credentials: str):
    super().__init__(name, provider="vertex_ai")
    self.vertex_credentials = vertex_credentials

  def _get_completion_kwargs(self):
    return {
        "response_format": {
            "type": "json_object"
        },
        "vertex_credentials": self.vertex_credentials
    }


supported_models: List[Model] = [
    Model("gpt-4o-2024-11-20"),
    Model("gpt-4o-mini-2024-07-18"),
    AnthropicModel("claude-3-5-sonnet-20241022"),
    AnthropicModel("claude-3-5-haiku-20241022"),
    VertexModel("gemini-1.5-pro-002",
                vertex_credentials=os.getenv("VERTEX_CREDENTIALS")),
    VertexModel("gemini-1.5-flash-002",
                vertex_credentials=os.getenv("VERTEX_CREDENTIALS")),
    Model("google/gemma-2-9b-it", provider="deepinfra"),
    Model("google/gemma-2-27b-it", provider="deepinfra"),
    Model("meta-llama/Meta-Llama-3.1-8B-Instruct", provider="deepinfra"),
    Model("meta-llama/Meta-Llama-3.1-70B-Instruct", provider="deepinfra"),
    Model("meta-llama/Meta-Llama-3.1-405B-Instruct", provider="deepinfra"),
    Model("meta-llama/Llama-3.2-3B-Instruct", provider="deepinfra"),
    Model("meta-llama/Llama-3.2-1B-Instruct", provider="deepinfra"),
    Model("Qwen/Qwen2.5-72B-Instruct", provider="deepinfra"),
]


def check_models(models: List[Model]):
  for model in models:
    print(f"Checking model {model.name}...")
    try:
      model.completion(
          """Output following this JSON format without using code blocks:
{"result": "your result here"}""", "How are you?")
      print(f"Model {model.name} is available.")

    # This check is designed to verify the availability of the models
    # without any issues. Therefore, we need to catch all exceptions.
    except Exception as e:  # pylint: disable=broad-except
      raise RuntimeError(f"Model {model.name} is not available: {e}") from e
