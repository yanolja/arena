"""
It provides a platform for comparing the responses of two LLMs. 
"""

from random import sample

from fastchat.serve import gradio_web_server
from fastchat.serve.gradio_web_server import bot_response
import gradio as gr

# TODO(#1): Add more models.
SUPPORTED_MODELS = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]


def user(user_message):
  model_pair = sample(SUPPORTED_MODELS, 2)
  new_state_a = gradio_web_server.State(model_pair[0])
  new_state_b = gradio_web_server.State(model_pair[1])

  for state in [new_state_a, new_state_b]:
    state.conv.append_message(state.conv.roles[0], user_message)
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
      # bot_response returns a generator yielding states and chatbots.
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

    for i in range(2):
      try:
        generator = next(generators[i])
        new_state = generator[0]
        new_states[i] = new_state
        # conv.messages is a list of [role, message].
        new_responses[i] = new_state.conv.messages[-1][-1]
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
  model_names = [gr.State(None), gr.State(None)]
  responses = [gr.State(None), gr.State(None)]

  # states stores FastChat-specific conversation states.
  states = [gr.State(None), gr.State(None)]

  prompt = gr.TextArea(label="Prompt", lines=4)
  submit = gr.Button()

  with gr.Row():
    responses[0] = gr.Textbox(label="Model A", interactive=False)
    responses[1] = gr.Textbox(label="Model B", interactive=False)

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
