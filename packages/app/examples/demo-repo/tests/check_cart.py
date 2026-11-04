import unittest

from shopsite.pages import cart_page, catalog_page


class Catalog(unittest.TestCase):
    def test_lists_every_product_with_a_price(self):
        page = catalog_page()
        for needle in ("Mug", "$8.00", "Sticker pack", "$3.00", "Poster", "$12.00"):
            self.assertIn(needle, page)


class Cart(unittest.TestCase):
    def test_total_is_price_times_quantity(self):
        self.assertIn("Total $19.00", cart_page())  # 2 mugs and 1 sticker pack

    def test_badge_counts_items_not_lines(self):
        self.assertIn("id='cart-count'>3 items<", cart_page())  # 2 mugs and 1 sticker pack are 3 items


if __name__ == "__main__":
    unittest.main()
