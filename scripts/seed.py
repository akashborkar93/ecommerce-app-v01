"""Idempotent demo data loader. Run manually: python -m scripts.seed

Products are matched by name, so running this repeatedly never creates duplicates.
Existing products are left untouched (stock and price edits are not overwritten).
"""
from decimal import Decimal

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import Product

DEMO_PRODUCTS = [
    {
        "name": "Wireless Headphones",
        "description": "Over-ear Bluetooth headphones with noise cancellation.",
        "price": Decimal("89.99"),
        "stock": 50,
        "category": "Electronics",
    },
    {
        "name": "Smart Watch",
        "description": "Fitness tracking smart watch with heart-rate monitor.",
        "price": Decimal("199.99"),
        "stock": 30,
        "category": "Electronics",
    },
    {
        "name": "Laptop",
        "description": "14-inch lightweight laptop, 16GB RAM, 512GB SSD.",
        "price": Decimal("1099.00"),
        "stock": 15,
        "category": "Computers",
    },
    {
        "name": "Water Bottle",
        "description": "Insulated stainless steel bottle, 750ml.",
        "price": Decimal("24.50"),
        "stock": 120,
        "category": "Home",
    },
]


def seed() -> tuple[int, int]:
    created = skipped = 0
    with get_sessionmaker()() as db:
        for data in DEMO_PRODUCTS:
            exists = db.scalar(select(Product.id).where(Product.name == data["name"]))
            if exists:
                skipped += 1
                continue
            db.add(Product(**data))
            created += 1
        db.commit()
    return created, skipped


if __name__ == "__main__":
    created, skipped = seed()
    print(f"Seed complete: {created} created, {skipped} already present.")
