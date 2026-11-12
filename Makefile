.PHONY: run test lint
run:
	uvicorn aerosafe.api.main:app --reload --app-dir src
test:
	pytest -q
lint:
	ruff check src tests eval
