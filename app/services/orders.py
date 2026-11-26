from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import InsufficientStockError, InvalidOrderError, NotFoundError
from app.models import Customer, Order, OrderItem, Product
from app.schemas.schemas import OrderCreate


def create_order(db: Session, data: OrderCreate) -> Order:
    if db.get(Customer, data.customer_id) is None:
        raise InvalidOrderError("Customer does not exist")

    # Merge duplicate product lines so each product is validated and decremented once.
    quantities: dict[int, int] = defaultdict(int)
    for item in data.items:
        quantities[item.product_id] += item.quantity

    products = {
        p.id: p for p in db.scalars(select(Product).where(Product.id.in_(quantities.keys())))
    }
    missing = sorted(set(quantities) - set(products))
    if missing:
        raise InvalidOrderError(f"Unknown product id(s): {missing}")

    order = Order(customer_id=data.customer_id, status="pending", total_amount=Decimal("0.00"))
    total = Decimal("0.00")
    try:
        for product_id, quantity in sorted(quantities.items()):
            # Atomic conditional decrement: prevents overselling under concurrent orders.
            result = db.execute(
                update(Product)
                .where(Product.id == product_id, Product.stock >= quantity)
                .values(stock=Product.stock - quantity)
            )
            if result.rowcount == 0:
                raise InsufficientStockError(
                    f"Insufficient stock for product {product_id}"
                )
            price = products[product_id].price
            total += price * quantity
            order.items.append(OrderItem(product_id=product_id, quantity=quantity, price=price))
        order.total_amount = total
        db.add(order)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_order(db, order.id)


def get_order(db: Session, order_id: int) -> Order:
    order = db.scalars(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    ).first()
    if order is None:
        raise NotFoundError("Order not found")
    return order


def list_orders(
    db: Session, customer_id: int | None, limit: int, offset: int
) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.id)
        .limit(limit)
        .offset(offset)
    )
    if customer_id is not None:
        stmt = stmt.where(Order.customer_id == customer_id)
    return list(db.scalars(stmt))
