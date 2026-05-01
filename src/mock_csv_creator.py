from faker import Faker
import pandas as pd
import random
import os
import shutil
from datetime import datetime, timedelta

fake = Faker("es_ES")

BASE_DIR = "tortilla_shops_reports"

# Predefined Spanish cities (realistic distribution)
SPANISH_CITIES = [
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza",
    "Málaga", "Murcia", "Palma", "Bilbao", "Alicante"
]

def generate_shop_metadata(num_shops=100):
    """
    Each shop has a fixed city + address
    Multiple shops can exist in same city
    """
    shops = {}

    for shop_id in range(1, num_shops + 1):
        city = random.choice(SPANISH_CITIES)

        shops[shop_id] = {
            "city": city,
            "address": fake.address().replace("\n", ", ")
        }

    return shops


def random_time_within_day(date_obj):
    """Generate random timestamp within the given day"""
    start = datetime.combine(date_obj, datetime.min.time())
    end = start + timedelta(days=1)
    return start + (end - start) * random.random()


def generate_shop_data(shop_id, shop_info, report_date, n_rows):
    data = []

    for _ in range(n_rows):
        data.append({
            "shop_id": shop_id,
            "transaction_id": fake.uuid4(),
            "customer_name": fake.name(),
            "city": shop_info["city"],
            "address": shop_info["address"],
            "timestamp": random_time_within_day(report_date),
            "tortilla_type": random.choice([
                "classic", "with_onion", "without_onion", "vegan"
            ]),
            "price": random.choice([
                round(random.uniform(5, 15), 2),
                None,
                "N/A"
            ]),
            "quantity": random.randint(1, 5)
        })

    return pd.DataFrame(data)


def generate_reports(report_date=None):
    # Handle date input
    if report_date:
        try:
            date_obj = datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be YYYY-MM-DD")
    else:
        date_obj = datetime.today()

    date_str = date_obj.strftime("%Y-%m-%d")

    os.makedirs(BASE_DIR, exist_ok=True)
    date_path = os.path.join(BASE_DIR, date_str)

    # Idempotent behavior
    if os.path.exists(date_path):
        print(f"[INFO] Overwriting existing data for {date_str}")
        shutil.rmtree(date_path)

    os.makedirs(date_path)

    print(f"[INFO] Generating reports for {date_str}")

    # Generate fixed shop metadata
    shops = generate_shop_metadata(100)

    for shop_id, shop_info in shops.items():
        n_rows = random.randint(50, 500)

        df = generate_shop_data(
            shop_id,
            shop_info,
            date_obj,
            n_rows
        )

        file_path = os.path.join(date_path, f"shop_{shop_id}.csv")
        df.to_csv(file_path, index=False)

    print(f"[DONE] Generated 100 CSVs for {date_str}")


if __name__ == "__main__":
    generate_reports("2026-05-01")