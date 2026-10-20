"""Fixed parameters for the scenario and the decision layer.

Anything here that is an *assumption* rather than a definition says so, because
those are the numbers a panel will ask about.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "flightline.sqlite"
MODEL_DIR = ROOT / "models"
STATIC_DIR = Path(__file__).resolve().parent / "static"

SEED = 26249
HORIZON_DAYS = 90

# Maintenance shift length used to turn repair man-hours into elapsed days.
CREW_HOURS_PER_DAY = 12.0

# GAO-01-587 (2001): a cannibalisation takes "at least twice the maintenance
# time of normal repairs" -- one removal from the donor plus one installation
# on the recipient, each as long as a normal replacement.
CANN_LABOUR_MULTIPLIER = 2.0

# ASSUMPTION. A component moved between airframes loses this fraction of its
# remaining life (handling, connector wear, re-rigging). GAO reports the effect
# qualitatively ("aggravate the very same supply problems") but gives no hazard
# figure, so the UI labels every number derived from this as modelled.
HANDLING_LIFE_PENALTY = 0.20

CANN_LOOKAHEAD_DAYS = 30

# Phase inspections may be inducted up to this many days before they fall due.
EARLY_INDUCTION_DAYS = 10

# Expediting an order (AOG priority freight) cuts its lead time to
# max(EXPEDITE_MIN_DAYS, EXPEDITE_FRACTION * lead). Budget per 90-day horizon.
EXPEDITE_BUDGET = 3
EXPEDITE_MIN_DAYS = 5
EXPEDITE_FRACTION = 0.3

CONFORMAL_ALPHA = 0.10  # 90% intervals

SURGE_WINDOW_DAYS = 14

# The CP-SAT search is capped in deterministic work units, not wall-clock
# seconds, so the same scenario always returns the same schedule.
CP_DETERMINISTIC_TIME = 1.0
