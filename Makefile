.PHONY: demo ollama-pull seed reset

# Use an activated Python 3.12+ venv (e.g. source .../fastapi_ai_venv_3.12/bin/activate)
# so `python` resolves to the env that has dependencies installed (`pip install -e .`).
demo:
	python -m uvicorn sms_demo.main:app --reload --host 0.0.0.0 --port 8000

ollama-pull:
	ollama pull llama3.1:8b-instruct-q4_K_M

seed:
	python scripts/seed_samples.py

reset:
	python scripts/reset_db.py
