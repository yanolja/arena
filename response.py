"""
This module contains functions for generating responses using LLMs.
"""

import enum
from random import sample

import gradio as gr
from litellm import completion

# TODO(#1): Add more models.
SUPPORTED_MODELS = [
    "gpt-4", "gpt-4-0125-preview", "gpt-3.5-turbo", "gemini-pro"
]


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

  models = sample(SUPPORTED_MODELS, 2)
  instruction = get_instruction(category, source_lang, target_lang)

  generators = []
  for model in models:
    try:
      # TODO(#1): Allow user to set configuration.
      response = completion(model=model,
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

        yield responses + models + [
            gr.Button(interactive=True) for _ in range(3)
        ] + [instruction, gr.Row(visible=False)]

      except StopIteration:
        pass

      # TODO(#1): Narrow down the exception type.
      except Exception as e:  # pylint: disable=broad-except
        print(f"Error in generator: {e}")
        raise e

    if stop:
      break
