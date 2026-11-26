from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.schemas import (
    CustomerCreate,
    CustomerRead,
    ErrorResponse,
    ProductCreate,
    ProductRead,
)
from app.services import catalog

products_router = APIRouter(prefix="/products", tags=["Products"])
customers_router = APIRouter(prefix="/customers", tags=["Customers"])


@products_router.get("", response_model=list[ProductRead], summary="List products")
def list_products(
    category: str | None = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return catalog.list_products(db, category, limit, offset)


@products_router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Get a product",
    responses={404: {"model": ErrorResponse, "description": "Product not found"}},
)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return catalog.get_product(db, product_id)


@products_router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
    responses={422: {"model": ErrorResponse, "description": "Validation error"}},
)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    return catalog.create_product(db, data)


@customers_router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer",
    responses={
        409: {"model": ErrorResponse, "description": "Email already exists"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    return catalog.create_customer(db, data)


@customers_router.get(
    "",
    response_model=list[CustomerRead],
    summary="List customers",
)
def list_customers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return catalog.list_customers(db, limit, offset)


@customers_router.get(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Get a customer",
    responses={404: {"model": ErrorResponse, "description": "Customer not found"}},
)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return catalog.get_customer(db, customer_id)
