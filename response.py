"""
This module contains functions for generating responses using LLMs.
"""

import enum
from random import sample
from uuid import uuid4

from firebase_admin import firestore
import gradio as gr

from leaderboard import db
from model import completion
from model import supported_models


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
    try:
      # TODO(#1): Allow user to set configuration.
      response = completion(model_name=model,
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
      print(f"Error with model {model}: {e}")
      raise gr.Error("Failed to get response. Please try again.")

  # It simulates concurrent stream response generation.
  max_response_length = max(len(response) for response in responses)
  for i in range(max_response_length):
    yield [response[:i + 1] for response in responses] + models + [instruction]

  yield responses + models + [instruction]
