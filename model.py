"""
This module contains functions to interact with the models.
"""

import json
import os
from typing import List

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

  def completion(self,
                 instruction: str,
                 prompt: str,
                 max_tokens: float = None) -> str:
    messages = [{
        "role":
            "system",
        "content":
            instruction + """
Output following this JSON format:
{"result": "your result here"}"""
    }, {
        "role": "user",
        "content": prompt
    }]

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
      return parsed_json["result"]

    except litellm.ContextWindowExceededError as e:
      raise ContextWindowExceededError() from e
    except json.JSONDecodeError as e:
      raise RuntimeError(f"Failed to get JSON response: {e}") from e

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
                 max_tokens: float = None) -> str:
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
    try:
      response = litellm.completion(
          model=self.provider + "/" + self.name if self.provider else self.name,
          api_key=self.api_key,
          api_base=self.api_base,
          messages=messages,
          max_tokens=max_tokens,
      )

    except litellm.ContextWindowExceededError as e:
      raise ContextWindowExceededError() from e

    result = response.choices[0].message.content
    if not result.endswith(suffix):
      raise RuntimeError(f"Failed to get the formatted response: {result}")

    return result.removesuffix(suffix).strip()


class EeveModel(Model):

  def _get_completion_kwargs(self):
    json_template = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string"
            }
        }
    }
    return {
        "extra_body": {
            "guided_json": json.dumps(json_template),
            "guided_decoding_backend": "lm-format-enforcer"
        }
    }


supported_models: List[Model] = [
    Model("gpt-4o-2024-05-13"),
    Model("gpt-4-turbo-2024-04-09"),
    Model("gpt-4-0125-preview"),
    Model("gpt-3.5-turbo-0125"),
    AnthropicModel("claude-3-opus-20240229"),
    AnthropicModel("claude-3-sonnet-20240229"),
    AnthropicModel("claude-3-haiku-20240307"),
    Model("mistral-small-2402", provider="mistral"),
    Model("mistral-large-2402", provider="mistral"),
    Model("llama3-8b-8192", provider="groq"),
    Model("llama3-70b-8192", provider="groq"),
    EeveModel("yanolja/EEVE-Korean-Instruct-10.8B-v1.0",
              provider="openai",
              api_base=os.getenv("EEVE_API_BASE"),
              api_key=os.getenv("EEVE_API_KEY")),
]


def check_models(models: List[Model]):
  for model in models:
    print(f"Checking model {model.name}...")
    try:
      model.completion("You are an AI model.", "Hello, world!")
      print(f"Model {model.name} is available.")

    # This check is designed to verify the availability of the models
    # without any issues. Therefore, we need to catch all exceptions.
    except Exception as e:  # pylint: disable=broad-except
      raise RuntimeError(f"Model {model.name} is not available: {e}") from e
