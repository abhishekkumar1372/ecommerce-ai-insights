export PYTHONPATH := $(CURDIR)/src
export DBT_PROFILES_DIR := $(CURDIR)/dbt

.PHONY: install sample download ingest transform pipeline test lint docs up

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

pipeline:    ## Sample data if none present, then ingest + transform
	@test -f data/raw/olist_orders_dataset.csv || $(MAKE) sample
	$(MAKE) ingest transform

test:        ## Python tests
	python -m pytest -q

lint:
	ruff check src tests

docs:        ## Browse the dbt lineage graph and column docs
	cd dbt && dbt docs generate && dbt docs serve

up:          ## Start Postgres + pgvector and run the pipeline in Docker
	docker compose up --build pipeline
