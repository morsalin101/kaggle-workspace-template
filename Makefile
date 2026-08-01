# =============================================================================
# Kaggle Workspace — run `make` on its own to see every command.
#
# Most targets take an optional project:   make push P=dl-finetune
# Omit P= and the default project (projects/.active) is used.
# =============================================================================

PYTHON ?= python3
VENV   ?= .venv

# Windows venvs put the interpreter in Scripts/, POSIX ones in bin/. Look for
# both so the same Makefile works under WSL, Git Bash, Linux and macOS.
VENV_PY := $(firstword $(wildcard $(VENV)/bin/python $(VENV)/Scripts/python.exe))

# Use the project venv when it exists, otherwise whatever python3 is active.
# You never have to `source .venv/bin/activate` — `make setup` builds it and
# every target reaches into it directly.
PY  := $(if $(VENV_PY),$(VENV_PY),$(PYTHON))
KWT := $(PY) -m kwt

# Accept lowercase p=/url= too — the uppercase form is easy to forget.
P   ?= $(p)
URL ?= $(url)

# Optional flags, e.g.  make push P=x WAIT=1 M="new features"
WAIT_FLAG    := $(if $(WAIT),--wait,)
FORCE_FLAG   := $(if $(FORCE),--force,)
REMOTE_FLAG  := $(if $(REMOTE),--remote,)
WATCH_FLAG   := $(if $(WATCH),--watch,)
OUTPUTS_FLAG := $(if $(OUTPUTS),--outputs,)
MESSAGE_FLAG := $(if $(M),-m "$(M)",)
TIMEOUT_FLAG := $(if $(TIMEOUT),--timeout $(TIMEOUT),)

.DEFAULT_GOAL := help
.PHONY: help setup new add rm sources validate push run status output pull list active clean check

help: ## Show this help
	@echo ""
	@echo "  Kaggle Workspace"
	@echo "  ----------------"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Options:  P=<project>  URL=<link>  WAIT=1  M=\"note\"  TIMEOUT=<sec>"
	@echo "            FORCE=1  REMOTE=1  WATCH=1  RECONFIGURE=1  NO_INPUT=1"
	@echo "  Example:  make push P=dl-finetune WAIT=1"
	@echo ""

# Probe by *running* the interpreter, not just checking the file exists — an
# interrupted setup can leave a .venv whose python is present but unusable.
setup: ## One-time: create .venv, install deps, write credentials, verify
	@if [ "$$(./$(VENV)/bin/python -c 'print(42)' 2>/dev/null)" != "42" ] && \
	   [ "$$(./$(VENV)/Scripts/python.exe -c 'print(42)' 2>/dev/null)" != "42" ]; then \
		if [ -e "$(VENV)" ]; then \
			echo "==> $(VENV)/ exists but its interpreter does not run — recreating"; \
			rm -rf "$(VENV)"; \
		fi; \
		echo "==> Creating virtualenv in $(VENV)/"; \
		$(PYTHON) -m venv "$(VENV)" || { \
			echo "Could not create a virtualenv with '$(PYTHON)'."; \
			echo "On Debian/Ubuntu:  sudo apt install python3-venv"; \
			echo "Or choose another interpreter:  make setup PYTHON=/path/to/python3"; \
			exit 1; }; \
	fi
	@VP=$$(ls $(VENV)/bin/python $(VENV)/Scripts/python.exe 2>/dev/null | head -1); \
		"$$VP" -m pip install --quiet --upgrade pip && \
		"$$VP" -m kwt setup $(if $(RECONFIGURE),--reconfigure,) \
			$(if $(P),--project "$(P)",) $(if $(NO_INPUT),--no-input,)

new: ## Create a new project folder            (make new P=my-run)
	@test -n "$(P)" || { echo "Usage: make new P=<project-name>"; exit 1; }
	@$(KWT) new $(P)

# URL is quoted so query strings (?select=a&b=c) survive the shell. Several
# links can still go in one call — separate them with spaces or commas.
add: ## Attach data by pasting its Kaggle link  (make add URL=<link>)
	@test -n "$(URL)" || { echo 'Usage: make add URL="https://www.kaggle.com/datasets/owner/name"'; exit 1; }
	@$(KWT) add "$(URL)" $(if $(P),-p $(P),)

rm: ## Detach a source by link or slug         (make rm URL=<link>)
	@test -n "$(URL)" || { echo 'Usage: make rm URL="owner/dataset-name"'; exit 1; }
	@$(KWT) rm "$(URL)" $(if $(P),-p $(P),)

sources: ## Show everything this project attaches
	@$(KWT) sources $(P)

validate: ## Check a project's config offline and preview its metadata
	@$(KWT) validate $(P)

push: ## Sync src/, upload the notebook, and start the run on Kaggle
	@$(KWT) push $(P) $(WAIT_FLAG) $(MESSAGE_FLAG) $(TIMEOUT_FLAG)

run: ## Push and block until the Kaggle run finishes
	@$(KWT) push $(P) --wait $(MESSAGE_FLAG) $(TIMEOUT_FLAG)

status: ## Show the latest run's status        (add WATCH=1 to poll)
	@$(KWT) status $(P) $(WATCH_FLAG)

output: ## Download run outputs into projects/<p>/outputs/
	@$(KWT) output $(P)

pull: ## Pull the notebook back from Kaggle    (FORCE=1 to overwrite)
	@$(KWT) pull $(P) $(FORCE_FLAG)

list: ## List local projects                   (REMOTE=1 to also list Kaggle)
	@$(KWT) list $(REMOTE_FLAG)

active: ## Show or set the default project      (make active P=my-run)
	@$(KWT) active $(P)

clean: ## Remove .build/                        (OUTPUTS=1 to empty outputs too)
	@$(KWT) clean $(OUTPUTS_FLAG)

check: ## Validate every project at once
	@$(KWT) list
	@for p in $$(ls projects 2>/dev/null); do \
		test -f "projects/$$p/config.yml" || continue; \
		echo ""; echo "--- $$p ---"; \
		$(KWT) validate $$p > /dev/null && echo "ok" || exit 1; \
	done
