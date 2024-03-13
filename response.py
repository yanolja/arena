"""
This module contains functions for generating responses using LLMs.
"""

import enum
import json
import os
from random import sample

from google.cloud import secretmanager
import gradio as gr
from litellm import completion

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
MODELS_SECRET = os.environ.get("MODELS_SECRET")

secretmanagerClient = secretmanager.SecretManagerServiceClient()
models_secret = secretmanagerClient.access_secret_version(
    name=secretmanagerClient.secret_version_path(GOOGLE_CLOUD_PROJECT,
                                                 MODELS_SECRET, "latest"))
decoded_secret = models_secret.payload.data.decode("UTF-8")

supported_models = json.loads(decoded_secret)


class Category(enum.Enum):
  SUMMARIZE = "Summarize"
  TRANSLATE = "Translate"


# TODO(#31): Let the model builders set the instruction.
def get_instruction(category, source_lang, target_lang):
  if category == Category.SUMMARIZE.value:
    return "Summarize the following text in its original language."
  if category == Category.TRANSLATE.value:
    return f"Translate the following text from {source_lang} to {target_lang}."


def response_generator(response: str):
  for part in response:
    content = part.choices[0].delta.content
    if content is None:
      continue

    # To simulate a stream, we yield each character of the response.
    for character in content:
      yield character


# TODO(#29): Return results simultaneously to prevent bias from generation speed.
def get_responses(user_prompt, category, source_lang, target_lang):
  if not category:
    raise gr.Error("Please select a category.")

  if category == Category.TRANSLATE.value and (not source_lang or
                                               not target_lang):
    raise gr.Error("Please select source and target languages.")

  models = sample(list(supported_models), 2)
  instruction = get_instruction(category, source_lang, target_lang)
  activated_vote_buttons = [gr.Button(interactive=True) for _ in range(3)]
  deactivated_vote_buttons = [gr.Button(interactive=False) for _ in range(3)]

  generators = []
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
                            }],
                            stream=True)
      generators.append(response_generator(response))

    # TODO(#1): Narrow down the exception type.
    except Exception as e:  # pylint: disable=broad-except
      print(f"Error in bot_response: {e}")
      raise e

  responses = ["", ""]

  # It simulates concurrent response generation from two models.
  while True:
    stop = True

    for i in range(len(generators)):
      try:
        yielded = next(generators[i])

        if yielded is None:
          continue

        responses[i] += yielded
        stop = False

        # model_name_row and vote_row are hidden during response generation.
        yield responses + models + deactivated_vote_buttons + [
            instruction,
            gr.Row(visible=False),
            gr.Row(visible=False)
        ]

      except StopIteration:
        pass

      # TODO(#1): Narrow down the exception type.
      except Exception as e:  # pylint: disable=broad-except
        print(f"Error in generator: {e}")
        raise e

    if stop:
      break

  # After generating the response, the vote_row should become visible,
  # while the model_name_row should remain hidden.
  yield responses + models + activated_vote_buttons + [
      instruction, gr.Row(visible=False),
      gr.Row(visible=True)
  ]
