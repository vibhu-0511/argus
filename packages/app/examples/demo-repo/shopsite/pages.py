"""The two pages of the demo shop, as plain functions that return HTML. All data is made up."""
from html import escape

CATALOG = [("mug", "Mug", 800), ("sticker", "Sticker pack", 300), ("poster", "Poster", 1200)]  # (sku, name, price in cents)
CART = [("mug", 2), ("sticker", 1)]  # (sku, quantity)


def money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def catalog_page() -> str:
    rows = "".join(f"<li>{escape(name)} <b>{money(price)}</b></li>" for _, name, price in CATALOG)
    return f"<h1>Demo shop</h1><ul id='catalog'>{rows}</ul><a href='/cart'>Cart</a>"


def cart_page(cart: list[tuple[str, int]] = CART) -> str:
    prices = {sku: (name, price) for sku, name, price in CATALOG}
    rows = "".join(f"<li>{qty} x {escape(prices[sku][0])}</li>" for sku, qty in cart)
    total = sum(prices[sku][1] * qty for sku, qty in cart)
    count = len(cart)
    return (f"<h1>Cart <span class='badge' id='cart-count'>{count} items</span></h1><ul id='lines'>{rows}</ul>"
            f"<p id='total'>Total {money(total)}</p><a href='/'>Keep shopping</a>")


PAGES = {"/": catalog_page, "/cart": cart_page}
