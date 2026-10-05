"""Constants for the OpenCook integration."""

from datetime import timedelta

DOMAIN = "opencook"
DEFAULT_PORT = 8080
UPDATE_INTERVAL = timedelta(seconds=2)
STATE_PATH = "/api/state"

STATUS_OPTIONS = ["standby", "cooking", "paused", "sleep", "error", "complete"]
RUNNING_STATUSES = {"cooking", "paused"}
