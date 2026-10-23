# Shortcuts for the commands in README.md ("Run it"). `make` alone runs setup, seed and the server.
PY  ?= python3
VENV = .venv
BIN  = $(VENV)/bin

.PHONY: all setup seed run test clean

all: seed run

$(BIN)/python:
	$(PY) -m venv $(VENV)

setup: $(BIN)/python  ## create .venv and install the pinned requirements
	$(BIN)/pip install -q -r requirements.txt

seed: setup  ## scenario, model and metrics (about a minute)
	$(BIN)/python -m flightline.seed

run:  ## dashboard on http://127.0.0.1:8000
	$(BIN)/uvicorn flightline.api:app --host 127.0.0.1 --port 8000

test:  ## the pytest suite
	$(BIN)/python -m pytest -q

clean:  ## generated scenario and model (rebuilt by `make seed`)
	rm -f data/flightline.sqlite
	rm -rf models
