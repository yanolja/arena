"""
It provides a platform for comparing the responses of two LLMs. 
"""

import enum
from random import sample
from uuid import uuid4

import firebase_admin
from firebase_admin import firestore
import gradio as gr
from litellm import completion

# TODO(#21): Fix auto-reload issue related to the initialization of Firebase.
db_app = firebase_admin.initialize_app()
db = firestore.client()

# TODO(#1): Add more models.
SUPPORTED_MODELS = [
    "gpt-4", "gpt-4-0125-preview", "gpt-3.5-turbo", "gemini-pro"
]

# TODO(#4): Add more languages.
SUPPORTED_TRANSLATION_LANGUAGES = ["Korean", "English"]


class ResponseType(enum.Enum):
  SUMMARIZE = "Summarize"
  TRANSLATE = "Translate"


class VoteOptions(enum.Enum):
  MODEL_A = "Model A is better"
  MODEL_B = "Model B is better"
  TIE = "Tie"


def vote(vote_button, response_a, response_b, model_a_name, model_b_name,
         user_prompt, res_type, source_lang, target_lang):
  doc_id = uuid4().hex
  winner = VoteOptions(vote_button).name.lower()

  if res_type == ResponseType.SUMMARIZE.value:
    doc_ref = db.collection("arena-summarizations").document(doc_id)
    doc_ref.set({
        "id": doc_id,
        "prompt": user_prompt,
        "model_a": model_a_name,
        "model_b": model_b_name,
        "model_a_response": response_a,
        "model_b_response": response_b,
        "winner": winner,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    return

  if res_type == ResponseType.TRANSLATE.value:
    doc_ref = db.collection("arena-translations").document(doc_id)
    doc_ref.set({
        "id": doc_id,
        "prompt": user_prompt,
        "model_a": model_a_name,
        "model_b": model_b_name,
        "model_a_response": response_a,
        "model_b_response": response_b,
        "source_language": source_lang.lower(),
        "target_language": target_lang.lower(),
        "winner": winner,
        "timestamp": firestore.SERVER_TIMESTAMP
    })


def response_generator(response: str):
  for part in response:
    content = part.choices[0].delta.content
    if content is None:
      continue

    # To simulate a stream, we yield each character of the response.
    for character in content:
      yield character


def get_responses(user_prompt):
  models = sample(SUPPORTED_MODELS, 2)

  generators = []
  for model in models:
    try:
      # TODO(#1): Allow user to set configuration.
      response = completion(model=model,
                            messages=[{
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

        yield responses + models

      except StopIteration:
        pass

      # TODO(#1): Narrow down the exception type.
      except Exception as e:  # pylint: disable=broad-except
        print(f"Error in generator: {e}")
        raise e

    if stop:
      break


with gr.Blocks() as app:
  with gr.Row():
    response_type_radio = gr.Radio(
        [response_type.value for response_type in ResponseType],
        label="Response type",
        info="Choose the type of response you want from the model.")

    source_language = gr.Dropdown(
        choices=SUPPORTED_TRANSLATION_LANGUAGES,
        label="Source language",
        info="Choose the source language for translation.",
        interactive=True,
        visible=False)
    target_language = gr.Dropdown(
        choices=SUPPORTED_TRANSLATION_LANGUAGES,
        label="Target language",
        info="Choose the target language for translation.",
        interactive=True,
        visible=False)

    def update_language_visibility(response_type):
      visible = response_type == ResponseType.TRANSLATE.value
      return {
          source_language: gr.Dropdown(visible=visible),
          target_language: gr.Dropdown(visible=visible)
      }

    response_type_radio.change(update_language_visibility, response_type_radio,
                               [source_language, target_language])

  model_names = [gr.State(None), gr.State(None)]
  response_boxes = [gr.State(None), gr.State(None)]

  prompt = gr.TextArea(label="Prompt", lines=4)
  submit = gr.Button()

  with gr.Row():
    response_boxes[0] = gr.Textbox(label="Model A", interactive=False)
    response_boxes[1] = gr.Textbox(label="Model B", interactive=False)

  # TODO(#5): Display it only after the user submits the prompt.
  # TODO(#6): Block voting if the response_type is not set.
  # TODO(#6): Block voting if the user already voted.
  with gr.Row():
    option_a = gr.Button(VoteOptions.MODEL_A.value)
    option_b = gr.Button("Model B is better")
    tie = gr.Button("Tie")

  # TODO(#7): Hide it until the user votes.
  with gr.Accordion("Show models", open=False):
    with gr.Row():
      model_names[0] = gr.Textbox(label="Model A", interactive=False)
      model_names[1] = gr.Textbox(label="Model B", interactive=False)

  submit.click(get_responses, prompt, response_boxes + model_names)

  common_inputs = response_boxes + model_names + [
      prompt, response_type_radio, source_language, target_language
  ]
  option_a.click(vote, [option_a] + common_inputs)
  option_b.click(vote, [option_b] + common_inputs)
  tie.click(vote, [tie] + common_inputs)

if __name__ == "__main__":
  # We need to enable queue to use generators.
  app.queue()
  app.launch(debug=True)
