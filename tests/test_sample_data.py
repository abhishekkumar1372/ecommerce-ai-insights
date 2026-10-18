from ecom.datasets import OLIST_FILES
from ecom.sample_data import generate


def test_generates_every_olist_file():
    assert set(generate(300)) == set(OLIST_FILES)


def test_is_deterministic():
    a, b = generate(300, seed=7), generate(300, seed=7)
    assert a["olist_orders_dataset.csv"]["order_id"].tolist() == b["olist_orders_dataset.csv"]["order_id"].tolist()


def test_items_reference_existing_orders_and_products():
    d = generate(500)
    items = d["olist_order_items_dataset.csv"]
    assert items["order_id"].isin(d["olist_orders_dataset.csv"]["order_id"]).all()
    assert items["product_id"].isin(d["olist_products_dataset.csv"]["product_id"]).all()


def test_plants_dirty_data_for_cleaning_models():
    d = generate(3000)
    translated = set(d["product_category_name_translation.csv"]["product_category_name"])
    categories = set(d["olist_products_dataset.csv"]["product_category_name"].dropna())
    assert categories - translated, "expected at least one untranslated category"
    reviews = d["olist_order_reviews_dataset.csv"]
    assert reviews.duplicated().any(), "expected duplicate review rows"
