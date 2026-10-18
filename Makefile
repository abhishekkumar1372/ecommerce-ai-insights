export PYTHONPATH := $(CURDIR)/src
export DBT_PROFILES_DIR := $(CURDIR)/dbt

.PHONY: install sample download ingest transform pipeline ai-setup summary anomalies api app evals test lint docs up

install:     ## Install Python dependencies
	pip install -r requirements.txt

sample:      ## Generate synthetic Olist-shaped data (no Kaggle account needed)
	python -m ecom.sample_data

download:    ## Download the real Olist dataset from Kaggle
	python -m ecom.download

ingest:      ## Load data/raw/*.csv into the raw schema
	python -m ecom.ingest

transform:   ## Build and test all dbt models
	cd dbt && dbt build

pipeline:    ## Sample data if none present, then ingest + transform + AI setup
	@test -f data/raw/olist_orders_dataset.csv || $(MAKE) sample
	$(MAKE) ingest transform ai-setup

ai-setup:    ## Create AI tables and index the retrieval knowledge base
	python -m ecom.ai.setup

summary:     ## Generate a fact-checked executive summary (needs ANTHROPIC_API_KEY)
	python -m ecom.ai.insights

anomalies:   ## List anomalous days and explain the top 3 (needs ANTHROPIC_API_KEY)
	python -m ecom.ai.anomalies --explain 3

api:         ## REST API on :8000
	uvicorn ecom.ai.api:app --reload

app:         ## Streamlit app on :8501
	streamlit run app/streamlit_app.py

evals:       ## Text-to-SQL accuracy + summary fact-check pass rate (needs ANTHROPIC_API_KEY)
	python -m ecom.ai.evals

test:        ## Python tests
	python -m pytest -q

lint:
	ruff check src tests app

docs:        ## Browse the dbt lineage graph and column docs
	cd dbt && dbt docs generate && dbt docs serve

up:          ## Start Postgres + pgvector and run the pipeline in Docker
	docker compose up --build pipeline
