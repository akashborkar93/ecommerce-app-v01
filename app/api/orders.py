from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.schemas import ErrorResponse, OrderCreate, OrderRead
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order",
    description="The total is calculated server-side from current product prices.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid order (unknown customer or product)"},
        409: {"model": ErrorResponse, "description": "Insufficient stock"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    return order_service.create_order(db, data)


@router.get("", response_model=list[OrderRead], summary="List orders")
def list_orders(
    customer_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return order_service.list_orders(db, customer_id, limit, offset)


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Get an order",
    responses={404: {"model": ErrorResponse, "description": "Order not found"}},
)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return order_service.get_order(db, order_id)
