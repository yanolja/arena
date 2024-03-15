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


def get_responses(user_prompt, category, source_lang, target_lang):
  if not category:
    raise gr.Error("Please select a category.")

  if category == Category.TRANSLATE.value and (not source_lang or
                                               not target_lang):
    raise gr.Error("Please select source and target languages.")

  models = sample(SUPPORTED_MODELS, 2)
  instruction = get_instruction(category, source_lang, target_lang)
  activated_vote_buttons = [gr.Button(interactive=True) for _ in range(3)]
  deactivated_vote_buttons = [gr.Button(interactive=False) for _ in range(3)]

  responses = []
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
                            }])
      responses.append(response.choices[0].message.content)

    # TODO(#1): Narrow down the exception type.
    except Exception as e:  # pylint: disable=broad-except
      print(f"Error in bot_response: {e}")
      raise e

  # It simulates concurrent stream response generation.
  max_response_length = max(len(response) for response in responses)
  for i in range(max_response_length):
    yield [response[:i + 1] for response in responses
          ] + models + deactivated_vote_buttons + [
              instruction,
              gr.Row(visible=False),
              gr.Row(visible=False)
          ]

  # After generating the response, the vote_row should become visible,
  # while the model_name_row should remain hidden.
  yield responses + models + activated_vote_buttons + [
      instruction, gr.Row(visible=False),
      gr.Row(visible=True)
  ]
