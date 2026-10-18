"""Generate a synthetic dataset with the exact shape of the Olist files.

Used by CI and for trying the pipeline without a Kaggle account. It plants the
same kinds of problems found in the real data, so the cleaning models are
exercised: duplicate reviews, missing delivery dates, untranslated categories,
inconsistent city casing and accents, and extreme freight values.

Usage:  python -m ecom.sample_data [--orders 5000] [--seed 42]
"""
import argparse
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from ecom.config import RAW_DIR

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "PE"]
STATE_WEIGHTS = [0.42, 0.13, 0.12, 0.06, 0.05, 0.04, 0.04, 0.03, 0.03, 0.08]
CITIES = {
    "SP": ["sao paulo", "campinas", "santos"], "RJ": ["rio de janeiro", "niteroi"],
    "MG": ["belo horizonte", "uberlandia"], "RS": ["porto alegre"], "PR": ["curitiba"],
    "SC": ["florianopolis"], "BA": ["salvador"], "DF": ["brasilia"], "GO": ["goiania"],
    "PE": ["recife"],
}
# Portuguese category -> (English name, typical price)
CATEGORIES = {
    "cama_mesa_banho": ("bed_bath_table", 90), "beleza_saude": ("health_beauty", 120),
    "esporte_lazer": ("sports_leisure", 110), "moveis_decoracao": ("furniture_decor", 140),
    "informatica_acessorios": ("computers_accessories", 160), "utilidades_domesticas": ("housewares", 85),
    "relogios_presentes": ("watches_gifts", 200), "telefonia": ("telephony", 70),
    "ferramentas_jardim": ("garden_tools", 105), "automotivo": ("auto", 130),
    "brinquedos": ("toys", 95), "eletronicos": ("electronics", 180),
    "pet_shop": ("pet_shop", 100),  # deliberately left out of the translation file
}
REVIEW_TEXT = {
    1: ["produto nao chegou", "entrega muito atrasada", "veio quebrado"],
    2: ["demorou demais", "qualidade ruim"],
    3: ["ok, nada demais", "chegou atrasado mas funciona"],
    4: ["bom produto", "recomendo"],
    5: ["otimo, chegou antes do prazo", "excelente qualidade", "perfeito"],
}


def _ids(n: int, rng: np.random.Generator) -> list[str]:
    return [uuid.UUID(int=int(rng.integers(0, 2**63)) << 64 | i).hex for i in range(n)]


def _city(state: str, rng: np.random.Generator) -> str:
    city = rng.choice(CITIES[state])
    # inconsistent formatting, as in the real file
    return {0: city, 1: city.upper(), 2: city.title()}[int(rng.integers(0, 3))] if rng.random() < 0.1 else city


def generate(n_orders: int = 5000, seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n_customers = int(n_orders * 0.9)
    n_products, n_sellers = max(50, n_orders // 20), max(20, n_orders // 60)

    unique_ids = _ids(int(n_customers * 0.97), rng)  # ~3% of people order twice or more
    cust_state = rng.choice(STATES, n_customers, p=STATE_WEIGHTS)
    customers = pd.DataFrame({
        "customer_id": _ids(n_customers, rng),
        "customer_unique_id": rng.choice(unique_ids, n_customers),
        "customer_zip_code_prefix": rng.integers(1000, 99999, n_customers).astype(str),
        "customer_city": [_city(s, rng) for s in cust_state],
        "customer_state": cust_state,
    })

    seller_state = rng.choice(STATES, n_sellers, p=STATE_WEIGHTS)
    sellers = pd.DataFrame({
        "seller_id": _ids(n_sellers, rng),
        "seller_zip_code_prefix": rng.integers(1000, 99999, n_sellers).astype(str),
        "seller_city": [_city(s, rng) for s in seller_state],
        "seller_state": seller_state,
    })

    cat_names = list(CATEGORIES)
    prod_cat = rng.choice(cat_names, n_products)
    products = pd.DataFrame({
        "product_id": _ids(n_products, rng),
        "product_category_name": np.where(rng.random(n_products) < 0.02, None, prod_cat),
        "product_name_lenght": rng.integers(10, 70, n_products),
        "product_description_lenght": rng.integers(50, 3000, n_products),
        "product_photos_qty": rng.integers(1, 8, n_products),
        "product_weight_g": rng.integers(100, 20000, n_products),
        "product_length_cm": rng.integers(10, 100, n_products),
        "product_height_cm": rng.integers(2, 80, n_products),
        "product_width_cm": rng.integers(8, 80, n_products),
    })
    base_price = np.array([CATEGORIES[c][1] for c in prod_cat]) * rng.lognormal(0, 0.5, n_products)

    # Purchases between 2017-01 and 2018-08 with growth and a Black Friday spike
    start = pd.Timestamp("2017-01-01")
    days = (pd.Timestamp("2018-08-31") - start).days
    day_weights = np.linspace(0.4, 1.6, days)
    bf = (pd.Timestamp("2017-11-24") - start).days
    day_weights[bf - 1:bf + 3] *= 4
    day_weights /= day_weights.sum()
    purchase = start + pd.to_timedelta(rng.choice(days, n_orders, p=day_weights), "D") \
        + pd.to_timedelta(rng.integers(0, 86400, n_orders), "s")

    status = rng.choice(["delivered", "shipped", "canceled", "unavailable", "invoiced", "processing"],
                        n_orders, p=[0.94, 0.02, 0.015, 0.01, 0.008, 0.007])
    est_days = rng.integers(15, 35, n_orders)
    actual_days = np.clip(rng.normal(12, 7, n_orders), 2, 60).round()
    delivered = purchase + pd.to_timedelta(actual_days, "D")
    orders = pd.DataFrame({
        "order_id": _ids(n_orders, rng),
        "customer_id": rng.choice(customers["customer_id"], n_orders, replace=False)
        if n_orders <= n_customers else rng.choice(customers["customer_id"], n_orders),
        "order_status": status,
        "order_purchase_timestamp": purchase,
        "order_approved_at": purchase + pd.to_timedelta(rng.integers(600, 86400, n_orders), "s"),
        "order_delivered_carrier_date": purchase + pd.to_timedelta(rng.integers(1, 5, n_orders), "D"),
        "order_delivered_customer_date": pd.Series(delivered).where(status == "delivered"),
        "order_estimated_delivery_date": (purchase + pd.to_timedelta(est_days, "D")).normalize(),
    })
    # ~1% of delivered orders are missing their delivery date in the source
    gap = (status == "delivered") & (rng.random(n_orders) < 0.01)
    orders.loc[gap, "order_delivered_customer_date"] = pd.NaT

    item_rows, pay_rows, review_rows = [], [], []
    seller_ids, product_ids = sellers["seller_id"].to_numpy(), products["product_id"].to_numpy()
    for o in orders.itertuples(index=False):
        n_items = int(rng.choice([1, 1, 1, 1, 2, 3]))
        total = 0.0
        for i in range(1, n_items + 1):
            p = int(rng.integers(0, n_products))
            price = round(float(base_price[p]), 2)
            freight = round(float(rng.gamma(2, 9)), 2)
            if rng.random() < 0.002:
                freight = round(freight * 25, 2)  # outlier
            item_rows.append((o.order_id, i, product_ids[p], rng.choice(seller_ids),
                              o.order_purchase_timestamp + pd.Timedelta(days=3), price, freight))
            total += price + freight
        if rng.random() < 0.05:  # voucher split
            pay_rows.append((o.order_id, 1, "voucher", 1, round(total * 0.3, 2)))
            pay_rows.append((o.order_id, 2, "credit_card", int(rng.integers(1, 10)), round(total * 0.7, 2)))
        else:
            ptype = rng.choice(["credit_card", "boleto", "debit_card"], p=[0.76, 0.2, 0.04])
            inst = int(rng.integers(1, 11)) if ptype == "credit_card" else 1
            pay_rows.append((o.order_id, 1, ptype, inst, round(total, 2)))

        if o.order_status in ("delivered", "canceled") or rng.random() < 0.3:
            late = (pd.notna(o.order_delivered_customer_date)
                    and o.order_delivered_customer_date > o.order_estimated_delivery_date)
            score = int(rng.choice([1, 2, 3, 4, 5], p=[0.35, 0.15, 0.2, 0.15, 0.15] if late
                                   else [0.06, 0.03, 0.08, 0.2, 0.63]))
            msg = rng.choice(REVIEW_TEXT[score]) if rng.random() < 0.45 else None
            created = (o.order_delivered_customer_date if pd.notna(o.order_delivered_customer_date)
                       else o.order_estimated_delivery_date).normalize() + pd.Timedelta(days=1)
            row = (uuid.UUID(int=int(rng.integers(0, 2**63))).hex, o.order_id, score, None, msg,
                   created, created + pd.Timedelta(hours=int(rng.integers(1, 72))))
            review_rows.append(row)
            if rng.random() < 0.01:
                review_rows.append(row)  # exact duplicate, as seen in the source

    order_items = pd.DataFrame(item_rows, columns=[
        "order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"])
    order_payments = pd.DataFrame(pay_rows, columns=[
        "order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"])
    order_reviews = pd.DataFrame(review_rows, columns=[
        "review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
        "review_creation_date", "review_answer_timestamp"])

    zips = pd.concat([customers[["customer_zip_code_prefix", "customer_city", "customer_state"]]
                      .set_axis(["zip", "city", "state"], axis=1),
                      sellers[["seller_zip_code_prefix", "seller_city", "seller_state"]]
                      .set_axis(["zip", "city", "state"], axis=1)]).drop_duplicates("zip")
    geolocation = pd.DataFrame({
        "geolocation_zip_code_prefix": zips["zip"],
        "geolocation_lat": rng.uniform(-33, -3, len(zips)).round(6),
        "geolocation_lng": rng.uniform(-60, -35, len(zips)).round(6),
        "geolocation_city": zips["city"], "geolocation_state": zips["state"],
    })
    translation = pd.DataFrame(
        [(pt, en) for pt, (en, _) in CATEGORIES.items() if pt != "pet_shop"],
        columns=["product_category_name", "product_category_name_english"])

    return {
        "olist_orders_dataset.csv": orders, "olist_order_items_dataset.csv": order_items,
        "olist_order_payments_dataset.csv": order_payments, "olist_order_reviews_dataset.csv": order_reviews,
        "olist_customers_dataset.csv": customers, "olist_sellers_dataset.csv": sellers,
        "olist_products_dataset.csv": products, "olist_geolocation_dataset.csv": geolocation,
        "product_category_name_translation.csv": translation,
    }


def write(out_dir: Path = RAW_DIR, n_orders: int = 5000, seed: int = 42) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in generate(n_orders, seed).items():
        df.to_csv(out_dir / name, index=False, date_format="%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    write(args.out, args.orders, args.seed)
    print(f"Wrote synthetic Olist-shaped data ({args.orders} orders) to {args.out}")


if __name__ == "__main__":
    main()
