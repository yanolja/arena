"""
This module contains functions for generating responses using LLMs.
"""

import enum
import logging
from random import sample
from typing import List
from uuid import uuid4

from firebase_admin import firestore
import gradio as gr

from db import db
from model import ContextWindowExceededError
from model import Model
from model import supported_models
import rate_limit
from rate_limit import rate_limiter

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# TODO(#37): Move DB operations to db.py.
def get_history_collection(category: str):
  if category == Category.SUMMARIZE.value:
    return db.collection("arena-summarization-history")

  if category == Category.TRANSLATE.value:
    return db.collection("arena-translation-history")


def create_history(category: str, model_name: str, instruction: str,
                   prompt: str, response: str):
  doc_id = uuid4().hex

  doc = {
      "id": doc_id,
      "model": model_name,
      "instruction": instruction,
      "prompt": prompt,
      "response": response,
      "timestamp": firestore.SERVER_TIMESTAMP
  }

  doc_ref = get_history_collection(category).document(doc_id)
  doc_ref.set(doc)


class Category(enum.Enum):
  SUMMARIZE = "Summarize"
  TRANSLATE = "Translate"


# TODO(#31): Let the model builders set the instruction.
def get_instruction(category: str, model: Model, source_lang: str,
                    target_lang: str):
  if category == Category.SUMMARIZE.value:
    return model.summarize_instruction

  if category == Category.TRANSLATE.value:
    return model.translate_instruction.format(source_lang=source_lang,
                                              target_lang=target_lang)


def get_responses(prompt: str, category: str, source_lang: str,
                  target_lang: str, token: str):
  if not category:
    raise gr.Error("Please select a category.")

  if category == Category.TRANSLATE.value and (not source_lang or
                                               not target_lang):
    raise gr.Error("Please select source and target languages.")

  try:
    rate_limiter.check_rate_limit(token)
  except rate_limit.InvalidTokenException as e:
    raise gr.Error(
        "Your session has expired. Please refresh the page to continue.") from e
  except rate_limit.UserRateLimitException as e:
    raise gr.Error(
        "You have made too many requests in a short period. Please try again later."  # pylint: disable=line-too-long
    ) from e
  except rate_limit.SystemRateLimitException as e:
    raise gr.Error(
        "Our service is currently experiencing high traffic. Please try again later."  # pylint: disable=line-too-long
    ) from e

  models: List[Model] = sample(list(supported_models), 2)
  responses = []
  got_invalid_response = False
  for model in models:
    instruction = get_instruction(category, model, source_lang, target_lang)
    try:
      # TODO(#1): Allow user to set configuration.
      response, is_parsed = model.completion(instruction, prompt)
      create_history(category, model.name, instruction, prompt, response)
      responses.append(response)

      if not is_parsed:
        got_invalid_response = True

    except ContextWindowExceededError as e:
      logger.exception("Context window exceeded for model %s.", model.name)
      raise gr.Error(
          "The prompt is too long. Please try again with a shorter prompt."
      ) from e
    except Exception as e:
      logger.exception("Failed to get response from model %s.", model.name)
      raise gr.Error("Failed to get response. Please try again.") from e

  if got_invalid_response:
    gr.Warning("An invalid response was received.")

  model_names = [model.name for model in models]

  # It simulates concurrent stream response generation.
  max_response_length = max(len(response) for response in responses)
  for i in range(max_response_length):
    yield [response[:i + 1] for response in responses
          ] + model_names + [instruction]

  yield responses + model_names + [instruction]
