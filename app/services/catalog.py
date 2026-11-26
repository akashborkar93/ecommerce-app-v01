from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Customer, Product
from app.schemas.schemas import CustomerCreate, ProductCreate


def list_products(db: Session, category: str | None, limit: int, offset: int) -> list[Product]:
    stmt = select(Product).order_by(Product.id).limit(limit).offset(offset)
    if category:
        stmt = stmt.where(Product.category == category)
    return list(db.scalars(stmt))


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return product


def create_product(db: Session, data: ProductCreate) -> Product:
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def create_customer(db: Session, data: CustomerCreate) -> Customer:
    customer = Customer(name=data.name, email=data.email.lower())
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A customer with this email already exists") from None
    db.refresh(customer)
    return customer


def list_customers(db: Session, limit: int, offset: int) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_customer(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer
