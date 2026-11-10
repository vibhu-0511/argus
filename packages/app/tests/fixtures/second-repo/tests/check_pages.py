import unittest

from tinysite.pages import PAGES


class Pages(unittest.TestCase):
    def test_home_greets(self):
        self.assertEqual(PAGES["/"], "Hello from tinysite")

    def test_about_exists(self):
        self.assertIn("/about", PAGES)


if __name__ == "__main__":
    unittest.main()
