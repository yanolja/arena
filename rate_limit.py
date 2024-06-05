"""
This module contains functions for rate limiting requests.
"""

import datetime
import signal
import sys
from uuid import uuid4

from apscheduler.schedulers import background
import gradio as gr


class InvalidTokenException(Exception):
  pass


class UserRateLimitException(Exception):
  pass


class SystemRateLimitException(Exception):
  pass


class RateLimiter:

  def __init__(self, limit=10000, period_in_seconds=60 * 60 * 24):
    # Maps tokens to the last time they made a request.
    # E.g, {"some-token": datetime.datetime(2021, 8, 1, 0, 0, 0)}
    self.requests = {}

    # The number of requests made.
    # This count is reset to zero at the end of each period.
    self.request_count = 0

    # The maximum number of requests allowed within the time period.
    self.limit = limit

    self.scheduler = background.BackgroundScheduler()
    self.scheduler.add_job(self.clean_up, "interval", seconds=60 * 60 * 24)
    self.scheduler.add_job(self.reset_request_count,
                           "interval",
                           seconds=period_in_seconds)
    self.scheduler.start()

  def request_allowed(self, token: str):
    if not token or token not in self.requests:
      raise InvalidTokenException()

    if (datetime.datetime.now() - self.requests[token]).seconds < 5:
      raise UserRateLimitException()

    if self.request_count >= self.limit:
      raise SystemRateLimitException()

    self.requests[token] = datetime.datetime.now()
    self.request_count += 1

  def initialize_request(self, token: str):
    self.requests[token] = datetime.datetime.min

  def clean_up(self):
    for token, last_request_time in dict(self.requests).items():
      if (datetime.datetime.now() - last_request_time).days >= 1:
        del self.requests[token]

  def reset_request_count(self):
    self.request_count = 0


rate_limiter = RateLimiter()


def set_token(app: gr.Blocks):

  def set_token_server():
    new_token = uuid4().hex
    rate_limiter.initialize_request(new_token)
    return new_token

  set_token_client = """
  function(newToken) {
    const expiresDateString = new Date(Date.now() + 24 * 60 * 60 * 1000).toUTCString();
    document.cookie = `token=${newToken}; expires=${expiresDateString};`;
  }
  """

  token = gr.Textbox(visible=False)
  app.load(fn=set_token_server, outputs=[token])
  token.change(fn=lambda _: None, js=set_token_client, inputs=[token])


def signal_handler(sig, frame):
  # We delete unused arguments to avoid a lint error.
  del sig, frame
  rate_limiter.scheduler.shutdown()
  sys.exit(0)


if gr.NO_RELOAD:
  # Catch signal to ensure scheduler shuts down when server stops.
  signal.signal(signal.SIGINT, signal_handler)
