# defcon-bench — Makefile
# Usage:
#   make fetch      # download pristine handouts (GCS / local cache)
#   make build      # build all service images (once; heavy: rust/haskell/racket)
#   make up         # bring up a full run (CTFd + services, fresh flags)
#   make reference RUN=<id>   # prove solvability: reference solvers vs live services
#   make agent RUN=<id>       # start the agent container
#   make score RUN=<id>       # pull CTFd scoreboard
#   make down RUN=<id>        # tear down
RUN ?= $(shell ls -td results/run-* 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null)

fetch:
	./fetch_handouts.sh

build:
	./orchestrator/build_all.sh

up:
	./orchestrator/up.sh

reference:
	./orchestrator/reference.sh $(RUN)

agent:
	./orchestrator/agent.sh $(RUN)

score:
	python3 orchestrator/scoreboard.py results/$(RUN)

down:
	./orchestrator/down.sh $(RUN)

.PHONY: fetch build up reference agent score down
