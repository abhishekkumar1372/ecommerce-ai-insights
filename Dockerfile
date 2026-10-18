FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app/src DBT_PROFILES_DIR=/app/dbt
# Same steps as `make pipeline`, without needing make in the image
CMD ["sh", "-c", "test -f data/raw/olist_orders_dataset.csv || python -m ecom.sample_data; python -m ecom.ingest && (cd dbt && dbt build) && python -m ecom.ai.setup"]
