"""
This module contains functions for generating responses using LLMs.
"""

import enum
import json
import os
from random import sample
from uuid import uuid4

from firebase_admin import firestore
from google.cloud import secretmanager
from google.oauth2 import service_account
import gradio as gr
from litellm import completion

from credentials import get_credentials_json
from leaderboard import db

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


def create_history(model_name: str, instruction: str, prompt: str,
                   response: str):
  doc_id = uuid4().hex

  doc = {
      "id": doc_id,
      "model": model_name,
      "instruction": instruction,
      "prompt": prompt,
      "response": response,
      "timestamp": firestore.SERVER_TIMESTAMP
  }

  doc_ref = db.collection("arena-history").document(doc_id)
  doc_ref.set(doc)


class Category(enum.Enum):
  SUMMARIZE = "Summarize"
  TRANSLATE = "Translate"


# TODO(#31): Let the model builders set the instruction.
def get_instruction(category, source_lang, target_lang):
  if category == Category.SUMMARIZE.value:
    return "Summarize the following text, maintaining the original language of the text in the summary."  # pylint: disable=line-too-long
  if category == Category.TRANSLATE.value:
    return f"Translate the following text from {source_lang} to {target_lang}."


def get_responses(user_prompt, category, source_lang, target_lang):
  if not category:
    raise gr.Error("Please select a category.")

  if category == Category.TRANSLATE.value and (not source_lang or
                                               not target_lang):
    raise gr.Error("Please select source and target languages.")

  models = sample(list(supported_models), 2)
  instruction = get_instruction(category, source_lang, target_lang)

  responses = []
  for model in models:
    model_config = supported_models[model]

    model_name = model_config[
        "provider"] + "/" + model if "provider" in model_config else model
    api_key = model_config.get("apiKey", None)
    api_base = model_config.get("apiBase", None)

    try:
      # TODO(#1): Allow user to set configuration.
      response = completion(model=model_name,
                            api_key=api_key,
                            api_base=api_base,
                            messages=[{
                                "content": instruction,
                                "role": "system"
                            }, {
                                "content": user_prompt,
                                "role": "user"
                            }])
      content = response.choices[0].message.content
      create_history(model, instruction, user_prompt, content)
      responses.append(content)

    # TODO(#1): Narrow down the exception type.
    except Exception as e:  # pylint: disable=broad-except
      print(f"Error in bot_response: {e}")
      raise e

  # It simulates concurrent stream response generation.
  max_response_length = max(len(response) for response in responses)
  for i in range(max_response_length):
    yield [response[:i + 1] for response in responses] + models + [instruction]

  yield responses + models + [instruction]
