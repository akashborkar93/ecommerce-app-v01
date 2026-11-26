from fastapi import FastAPI

from app.api import catalog, health, orders
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import request_context_middleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.service_name)

    app = FastAPI(
        title="E-Commerce API",
        version="0.1.0",
        description="Simple e-commerce backend: products, customers and orders.",
    )
    app.middleware("http")(request_context_middleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(catalog.products_router)
    app.include_router(catalog.customers_router)
    app.include_router(orders.router)
    return app


app = create_app()
