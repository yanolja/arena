"""
It provides a platform for comparing the responses of two LLMs. 
"""

import enum
import json
from random import sample
from uuid import uuid4

from fastchat.serve import gradio_web_server
from fastchat.serve.gradio_web_server import bot_response
import firebase_admin
from firebase_admin import firestore
import gradio as gr

db_app = firebase_admin.initialize_app()
db = firestore.client()

# TODO(#1): Add more models.
SUPPORTED_MODELS = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gemini-pro"]

# TODO(#1): Add more languages.
SUPPORTED_TRANSLATION_LANGUAGES = ["Korean", "English"]


class ResponseType(enum.Enum):
  SUMMARIZE = "Summarize"
  TRANSLATE = "Translate"


class VoteOptions(enum.Enum):
  MODEL_A = "Model A is better"
  MODEL_B = "Model B is better"
  TIE = "Tie"


def vote(state_a, state_b, vote_button, res_type, source_lang, target_lang):
  winner = VoteOptions(vote_button).name.lower()

  # The 'messages' field in the state is an array of arrays, a data type
  # not supported by Firestore. Therefore, we convert it to a JSON string.
  model_a_conv = json.dumps(state_a.dict())
  model_b_conv = json.dumps(state_b.dict())

  if res_type == ResponseType.SUMMARIZE.value:
    doc_ref = db.collection("arena-summarizations").document(uuid4().hex)
    doc_ref.set({
        "model_a": state_a.model_name,
        "model_b": state_b.model_name,
        "model_a_conv": model_a_conv,
        "model_b_conv": model_b_conv,
        "winner": winner,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    return

  if res_type == ResponseType.TRANSLATE.value:
    doc_ref = db.collection("arena-translations").document(uuid4().hex)
    doc_ref.set({
        "model_a": state_a.model_name,
        "model_b": state_b.model_name,
        "model_a_conv": model_a_conv,
        "model_b_conv": model_b_conv,
        "source_language": source_lang.lower(),
        "target_language": target_lang.lower(),
        "winner": winner,
        "timestamp": firestore.SERVER_TIMESTAMP
    })


def user(user_prompt):
  model_pair = sample(SUPPORTED_MODELS, 2)
  new_state_a = gradio_web_server.State(model_pair[0])
  new_state_b = gradio_web_server.State(model_pair[1])

  for state in [new_state_a, new_state_b]:
    state.conv.append_message(state.conv.roles[0], user_prompt)
    state.conv.append_message(state.conv.roles[1], None)
    state.skip_next = False

  return [
      new_state_a, new_state_b, new_state_a.model_name, new_state_b.model_name
  ]


def bot(state_a, state_b, request: gr.Request):
  new_states = [state_a, state_b]

  generators = []
  for state in new_states:
    try:
      # TODO(#1): Allow user to set configuration.
      # bot_response returns a generator yielding states.
      generator = bot_response(state,
                               temperature=0.9,
                               top_p=0.9,
                               max_new_tokens=100,
                               request=request)
      generators.append(generator)

    # TODO(#1): Narrow down the exception type.
    except Exception as e:  # pylint: disable=broad-except
      print(f"Error in bot_response: {e}")
      raise e

  new_responses = [None, None]

  # It simulates concurrent response generation from two models.
  while True:
    stop = True

    for i in range(len(generators)):
      try:
        yielded = next(generators[i])

        # The generator yields a tuple, with the new state as the first item.
        new_state = yielded[0]
        new_states[i] = new_state

        # The last item from 'messages' represents the response to the prompt.
        bot_message = new_state.conv.messages[-1]

        # Each message in conv.messages is structured as [role, message],
        # so we extract the last message component.
        new_responses[i] = bot_message[-1]

        stop = False

      except StopIteration:
        pass

      # TODO(#1): Narrow down the exception type.
      except Exception as e:  # pylint: disable=broad-except
        print(f"Error in generator: {e}")
        raise e

    yield new_states + new_responses

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
      if response_type != ResponseType.TRANSLATE.value:
        return {
            source_language: gr.Dropdown(visible=False),
            target_language: gr.Dropdown(visible=False)
        }

      return {
          source_language: gr.Dropdown(visible=True),
          target_language: gr.Dropdown(visible=True)
      }

    response_type_radio.change(update_language_visibility, response_type_radio,
                               [source_language, target_language])

  model_names = [gr.State(None), gr.State(None)]
  responses = [gr.State(None), gr.State(None)]

  # states stores FastChat-specific conversation states.
  states = [gr.State(None), gr.State(None)]

  prompt = gr.TextArea(label="Prompt", lines=4)
  submit = gr.Button()

  with gr.Row():
    responses[0] = gr.Textbox(label="Model A", interactive=False)
    responses[1] = gr.Textbox(label="Model B", interactive=False)

  # TODO(#1): Display it only after the user submits the prompt.
  # TODO(#1): Block voting if the response_type is not set.
  # TODO(#1): Block voting if the user already voted.
  with gr.Row():
    option_a = gr.Button(VoteOptions.MODEL_A.value)
    option_a.click(
        vote, states +
        [option_a, response_type_radio, source_language, target_language])

    option_b = gr.Button("Model B is better")
    option_b.click(
        vote, states +
        [option_b, response_type_radio, source_language, target_language])

    tie = gr.Button("Tie")
    tie.click(
        vote,
        states + [tie, response_type_radio, source_language, target_language])

  # TODO(#1): Hide it until the user votes.
  with gr.Accordion("Show models", open=False):
    with gr.Row():
      model_names[0] = gr.Textbox(label="Model A", interactive=False)
      model_names[1] = gr.Textbox(label="Model B", interactive=False)

  submit.click(user, prompt, states + model_names,
               queue=False).then(bot, states, states + responses)

if __name__ == "__main__":
  # We need to enable queue to use generators.
  app.queue()
  app.launch(debug=True)
