from tinydb import Query

from app.database import carts_collection, orders_collection, products_collection
from app.services.commerce import (
    add_to_cart,
    checkout_cart,
    get_or_create_cart,
    get_product,
    search_products,
)
from app.services.commerce_tools import execute_commerce_tool


def test_search_returns_catalog_product():
    products = search_products("wireless headphones")

    assert [product["product_id"] for product in products] == [
        "prod-headphones-001"
    ]


def test_checkout_applies_allowed_coupon_and_decrements_inventory(test_customer):
    product_id = "prod-headphones-001"
    original_inventory = get_product(product_id)["inventory"]

    try:
        add_to_cart(test_customer, product_id, 1)
        order = checkout_cart(test_customer, "TECH10")

        assert order["status"] == "paid"
        assert order["discount_percent"] == 10
        assert get_product(product_id)["inventory"] == original_inventory - 1
        assert get_or_create_cart(test_customer)["status"] == "open"
    finally:
        products_collection.update(
            {"inventory": original_inventory},
            Query().product_id == product_id,
        )
        orders_collection.remove(Query().customer_id == test_customer)
        carts_collection.remove(Query().customer_id == test_customer)


def test_checkout_tool_requires_explicit_confirmation(test_customer):
    result = execute_commerce_tool(
        "checkout",
        {"coupon_code": "TECH10"},
        test_customer,
    )

    assert "error" in result
    assert "explicit purchase confirmation" in result["error"]


def test_unknown_tool_is_rejected(test_customer):
    result = execute_commerce_tool("delete_all_orders", {}, test_customer)

    assert result == {"error": "Unsupported commerce tool 'delete_all_orders'."}
