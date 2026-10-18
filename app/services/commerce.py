"""Deterministic commerce operations used by the simulated store."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.database import (
    carts_collection,
    customers_collection,
    orders_collection,
    products_collection,
)
from app.domain import MAX_DISCOUNT_PERCENT, STANDARD_COUPON_CODE


class CommerceError(Exception):
    """Base error for a rejected commerce operation."""


class NotFoundError(CommerceError):
    """Raised when a requested commerce record does not exist."""


class ValidationError(CommerceError):
    """Raised when a commerce operation violates a business rule."""


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def seed_commerce_data() -> None:
    """Insert the stable demo dataset without duplicating existing records."""
    if not products_collection.all():
        products_collection.insert_multiple(
            [
                {
                    "product_id": "prod-laptop-001",
                    "name": "TechMart Pro Laptop",
                    "description": "14-inch productivity laptop with 16 GB RAM.",
                    "price": 1299.99,
                    "inventory": 8,
                    "image_url": None,
                },
                {
                    "product_id": "prod-headphones-001",
                    "name": "TechMart Wireless Headphones",
                    "description": "Noise-cancelling wireless headphones.",
                    "price": 149.99,
                    "inventory": 20,
                    "image_url": None,
                },
                {
                    "product_id": "prod-keyboard-001",
                    "name": "TechMart Mechanical Keyboard",
                    "description": "Compact mechanical keyboard with USB-C.",
                    "price": 89.99,
                    "inventory": 15,
                    "image_url": None,
                },
            ]
        )

    if not customers_collection.all():
        customers_collection.insert(
            {
                "customer_id": "customer-demo-001",
                "name": "Demo Customer",
                "email": "demo.customer@example.test",
            }
        )


def ensure_sandbox_customer(company_id: str) -> str:
    """Return (creating on first use) the isolated demo customer of a company.

    Commerce endpoints never trust a client-supplied customer ID: each tenant
    gets its own sandbox customer, so one company can never read or check out
    another company's cart.
    """
    customer_id = f"sandbox-{company_id}"
    if customers_collection.get(customer_id=customer_id) is None:
        customers_collection.insert(
            {
                "customer_id": customer_id,
                "company_id": company_id,
                "name": "Sandbox Customer",
                "email": f"{customer_id}@example.test",
            }
        )
    return customer_id


def get_product(product_id: str) -> dict:
    product = products_collection.get(product_id=product_id)
    if product is None:
        raise NotFoundError(f"Product '{product_id}' was not found.")
    return dict(product)


def search_products(search_term: str = "") -> list[dict]:
    term = search_term.strip().lower()
    products = products_collection.all()
    if not term:
        return [dict(product) for product in products]
    return [
        dict(product)
        for product in products
        if term in product["name"].lower()
        or term in product["description"].lower()
    ]


def get_or_create_cart(customer_id: str) -> dict:
    if customers_collection.get(customer_id=customer_id) is None:
        raise NotFoundError(f"Customer '{customer_id}' was not found.")

    cart = carts_collection.get(customer_id=customer_id)
    if cart is None:
        cart = {
            "customer_id": customer_id,
            "items": [],
            "status": "open",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        carts_collection.insert(cart)
    elif cart["status"] != "open":
        cart = {
            **cart,
            "items": [],
            "status": "open",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        carts_collection.update(cart, customer_id=customer_id)
    return dict(cart)


def add_to_cart(customer_id: str, product_id: str, quantity: int) -> dict:
    if quantity < 1 or quantity > 20:
        raise ValidationError("Quantity must be between 1 and 20.")

    cart = get_or_create_cart(customer_id)
    product = get_product(product_id)
    existing_quantity = next(
        (item["quantity"] for item in cart["items"] if item["product_id"] == product_id),
        0,
    )
    requested_quantity = existing_quantity + quantity
    if requested_quantity > product["inventory"]:
        raise ValidationError("Requested quantity exceeds available inventory.")

    updated_items = [
        item for item in cart["items"] if item["product_id"] != product_id
    ]
    updated_items.append(
        {
            "product_id": product_id,
            "name": product["name"],
            "unit_price": product["price"],
            "quantity": requested_quantity,
        }
    )
    updated_cart = {
        **cart,
        "items": updated_items,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    carts_collection.update(
        updated_cart, customer_id=customer_id
    )
    return updated_cart


def calculate_cart_total(cart: dict, coupon_code: str | None = None) -> dict:
    subtotal = sum(
        Decimal(str(item["unit_price"])) * item["quantity"] for item in cart["items"]
    )
    discount_percent = MAX_DISCOUNT_PERCENT if coupon_code == STANDARD_COUPON_CODE else 0
    discount = subtotal * Decimal(discount_percent) / Decimal(100)
    return {
        "subtotal": _money(subtotal),
        "discount_percent": discount_percent,
        "discount": _money(discount),
        "total": _money(subtotal - discount),
    }


def checkout_cart(customer_id: str, coupon_code: str | None = None) -> dict:
    cart = get_or_create_cart(customer_id)
    if cart["status"] != "open":
        raise ValidationError("Only open carts can be checked out.")
    if not cart["items"]:
        raise ValidationError("Cannot check out an empty cart.")

    for item in cart["items"]:
        product = get_product(item["product_id"])
        if item["quantity"] > product["inventory"]:
            raise ValidationError(
                f"Insufficient inventory for product '{item['product_id']}'."
            )

    totals = calculate_cart_total(cart, coupon_code)
    for item in cart["items"]:
        product = get_product(item["product_id"])
        products_collection.update(
            {"inventory": product["inventory"] - item["quantity"]},
            product_id=item["product_id"],
        )

    order = {
        "order_id": f"order-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "customer_id": customer_id,
        "items": cart["items"],
        **totals,
        "status": "paid",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    orders_collection.insert(order)
    carts_collection.update(
        {
            "items": [],
            "status": "checked_out",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        customer_id=customer_id,
    )
    return order
