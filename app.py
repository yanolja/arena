from random import sample

import gradio as gr
from fastchat.serve import gradio_web_server
from fastchat.serve.gradio_web_server import bot_response

# TODO(#1): Add more models.
SUPPORTED_MODELS = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]


def user(state_a, state_b, user_message):
  if state_a is None and state_b is None:
    model_pair = sample(SUPPORTED_MODELS, 2)
    state_a = gradio_web_server.State(model_pair[0])
    state_b = gradio_web_server.State(model_pair[1])

  for state in [state_a, state_b]:
    state.conv.append_message(state.conv.roles[0], user_message)
    state.conv.append_message(state.conv.roles[1], None)
    state.skip_next = False

  empty_prompt = ""

  return [
      state_a, state_b,
      state_a.to_gradio_chatbot(),
      state_b.to_gradio_chatbot(), state_a.model_name, state_b.model_name,
      empty_prompt
  ]


def bot(state_a, state_b, request: gr.Request):
  if state_a is None or state_b is None:
    raise RuntimeError(f"states cannot be None, got [{state_a}, {state_b}]")

  generators = []
  for state in [state_a, state_b]:
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

  new_chatbots = [None, None]
  while True:
    stop = True

    for i in range(2):
      try:
        generator = next(generators[i])
        states[i], new_chatbots[i] = generator[0], generator[1]
        stop = False
      except StopIteration:
        pass

    yield [state_a, state_b] + new_chatbots

    if stop:
      break


with gr.Blocks() as app:
  with gr.Row():
    response_type = gr.Radio(
        ["Summarization", "Translation"],
        value="Summarization",
        label="Response type",
        info="Choose the type of response you want from the model.")
    language = gr.Dropdown(["Korean", "English"],
                           value="Korean",
                           label="Language",
                           info="Choose the target language.")

  chatbots = [None, None]
  with gr.Row():
    chatbots[0] = gr.Chatbot(label="Model A")
    chatbots[1] = gr.Chatbot(label="Model B")

  model_names = [None, None]
  with gr.Accordion("Show models", open=False):
    with gr.Row():
      model_names[0] = gr.Textbox(label="Model A", interactive=False)
      model_names[1] = gr.Textbox(label="Model B", interactive=False)

  prompt = gr.Textbox(label="Prompt")

  states = [gr.State(None), gr.State(None)]
  prompt.submit(user,
                states + [prompt],
                states + chatbots + model_names + [prompt],
                queue=False).then(bot, states, states + chatbots)

if __name__ == "__main__":
  # We need to enable queue to use generators.
  app.queue()
  app.launch()
