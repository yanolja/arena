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
    ip_address = request.client.host

    if ip_address in self.requests and self.within_limit(
        self.requests[ip_address]):
      return False

    self.requests[ip_address] = datetime.datetime.now()
    return True

  def clean_up(self):
    for ip_address, last_request_time in dict(self.requests).items():
      if not self.within_limit(last_request_time):
        del self.requests[ip_address]

  def within_limit(self, target_time: datetime.datetime) -> bool:
    return (datetime.datetime.now() - target_time).seconds < 30


rate_limiter = RateLimiter()
scheduler = background.BackgroundScheduler()
scheduler.add_job(rate_limiter.clean_up, "interval", seconds=60 * 60 * 24)
scheduler.start()


def signal_handler(sig, frame):
  del sig, frame
  scheduler.shutdown()
  sys.exit(0)


if gr.NO_RELOAD:
  signal.signal(signal.SIGINT, signal_handler)
