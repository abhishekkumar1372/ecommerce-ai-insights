"""The Olist source files and the raw table each one loads into."""

# file name in data/raw  ->  table name in the `raw` schema
OLIST_FILES: dict[str, str] = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_customers_dataset.csv": "customers",
    "olist_sellers_dataset.csv": "sellers",
    "olist_products_dataset.csv": "products",
    "olist_geolocation_dataset.csv": "geolocation",
    "product_category_name_translation.csv": "product_category_name_translation",
}

KAGGLE_DATASET = "olistbr/brazilian-ecommerce"
