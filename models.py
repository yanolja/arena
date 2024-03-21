"""
This module contains functions to interact with the models.
"""

import json
import os
from typing import List

from google.cloud import secretmanager
from google.oauth2 import service_account
import litellm

from credentials import get_credentials_json

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
MODELS_SECRET = os.environ.get("MODELS_SECRET")

secretmanager_client = secretmanager.SecretManagerServiceClient(
    credentials=service_account.Credentials.from_service_account_info(
        get_credentials_json()))
models_secret = secretmanager_client.access_secret_version(
    name=secretmanager_client.secret_version_path(GOOGLE_CLOUD_PROJECT,
                                                  MODELS_SECRET, "latest"))
decoded_secret = models_secret.payload.data.decode("UTF-8")

supported_models = json.loads(decoded_secret)


def completion(model: str, messages: List, max_tokens: float = None) -> str:
  model_config = supported_models[model]
  model_name = model_config[
      "provider"] + "/" + model if "provider" in model_config else model
  api_key = model_config.get("apiKey", None)
  api_base = model_config.get("apiBase", None)

  response = litellm.completion(model=model_name,
                                api_key=api_key,
                                api_base=api_base,
                                messages=messages,
                                max_tokens=max_tokens)
  return response.choices[0].message.content


def check_all_models() -> bool:
  for model in supported_models:
    try:
      completion(model=model,
                 messages=[{
                     "content": "Hello.",
                     "role": "user"
                 }],
                 max_tokens=5)
    except Exception as e:  # pylint: disable=broad-except
      raise RuntimeError(f"Model {model} is not available: {e}") from e
