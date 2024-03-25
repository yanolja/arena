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

supported_models_json = json.loads(decoded_secret)


class Model:

  def __init__(
      self,
      name: str,
      provider: str = None,
      # The JSON keys are in camelCase. To unpack these keys into
      # Model attributes, we need to use the same camelCase names.
      apiKey: str = None,  # pylint: disable=invalid-name
      apiBase: str = None):  # pylint: disable=invalid-name
    self.name = name
    self.provider = provider
    self.api_key = apiKey
    self.api_base = apiBase


supported_models: List[Model] = [
    Model(name=model_name, **model_config)
    for model_name, model_config in supported_models_json.items()
]


def completion(model_name: str,
               messages: List,
               max_tokens: float = None) -> str:
  model = next(
      (model for model in supported_models if model.name == model_name), None)

  response = litellm.completion(model=model.provider + "/" +
                                model_name if model.provider else model_name,
                                api_key=model.api_key,
                                api_base=model.api_base,
                                messages=messages,
                                max_tokens=max_tokens)

  return response.choices[0].message.content


def check_models(models: List[Model]):
  for model in models:
    try:
      completion(model_name=model.name,
                 messages=[{
                     "content": "Hello.",
                     "role": "user"
                 }],
                 max_tokens=5)

    # This check is designed to verify the availability of the models
    # without any issues. Therefore, we need to catch all exceptions.
    except Exception as e:  # pylint: disable=broad-except
      raise RuntimeError(f"Model {model.name} is not available: {e}") from e
