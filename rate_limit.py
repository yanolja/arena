"""
This module contains functions for rate limiting requests.
"""

import datetime
import signal
import sys

from apscheduler.schedulers import background
import gradio as gr


class RateLimiter:

  def __init__(self):
    self.requests = {}

  def request_allowed(self, request: gr.Request) -> bool:
    for cookie in request.headers["cookie"].split("; "):
      name, value = cookie.split("=")
      if name == "token":
        token = value
        break
    else:
      return False

    if not token or token not in self.requests:
      return False

    if (datetime.datetime.now() - self.requests[token]).seconds < 5:
      return False

    self.requests[token] = datetime.datetime.now()
    return True

  def initialize_request(self, token: str):
    self.requests[token] = datetime.datetime.min

  def clean_up(self):
    for ip_address, last_request_time in dict(self.requests).items():
      if (datetime.datetime.now() - last_request_time).days >= 1:
        del self.requests[ip_address]


rate_limiter = RateLimiter()


def set_token(app: gr.Blocks):

  def set_token_server(new_token: str):
    rate_limiter.initialize_request(new_token)
    return new_token

  # It's designated for the 'js' parameter in the app.load method.
  # In Gradio, the 'js' method runs before the 'fn' method,
  # therefore it is used to set the token on the client side first.
  set_token_client = """
  function(_) {
    const newToken = crypto.randomUUID();
    const expiresDateString = new Date(Date.now() + 24 * 60 * 60 * 1000).toUTCString();
    document.cookie = `token=${newToken}; expires=${expiresDateString};`;
    return newToken;
  }
  """

  token = gr.Textbox(visible=False)
  app.load(fn=set_token_server,
           js=set_token_client,
           inputs=[token],
           outputs=[token])


scheduler = background.BackgroundScheduler()
scheduler.add_job(rate_limiter.clean_up, "interval", seconds=60 * 60 * 24)
scheduler.start()


def signal_handler(sig, frame):
  del sig, frame
  scheduler.shutdown()
  sys.exit(0)


if gr.NO_RELOAD:
  # Catch signal to ensure scheduler shuts down when server stops.
  signal.signal(signal.SIGINT, signal_handler)
