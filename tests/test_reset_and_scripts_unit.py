import unittest

from scripts.reset_database import BUSINESS_COLLECTIONS, RESET_CONFIRMATION, build_reset_plan, mask_uri


class ResetAndScriptsUnitTests(unittest.TestCase):
    def test_mask_uri_hides_credentials(self):
        uri = "mongodb+srv://user:secret@cluster0.example.mongodb.net/?retryWrites=true&w=majority"
        masked = mask_uri(uri)
        self.assertIn("***:***@", masked)
        self.assertNotIn("secret", masked)
        self.assertIn("cluster0.example.mongodb.net", masked)

    def test_build_business_reset_plan(self):
        plan = build_reset_plan("business")
        self.assertEqual(plan["collections_to_drop"], BUSINESS_COLLECTIONS)
        self.assertIn("products", plan["collections_to_keep"])
        self.assertIn("reset stock_reserved to 0 on every variant size", plan["post_actions"])

    def test_build_full_reset_plan(self):
        plan = build_reset_plan("full")
        self.assertEqual(plan["collections_to_drop"], "ALL_APPLICATION_COLLECTIONS")
        self.assertEqual(plan["collections_to_keep"], [])

    def test_reset_confirmation_phrase_is_strict(self):
        self.assertEqual(RESET_CONFIRMATION, "RESET SAVAGE RISE DATABASE")


if __name__ == "__main__":
    unittest.main()
