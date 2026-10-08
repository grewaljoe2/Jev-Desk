"""Regression: comparative BOOK must use the same advisory lock as standalone BOOK."""
import inspect
import unittest
from app.research import savip_book
from app.storage import db

class BookLockTests(unittest.TestCase):
    def test_comparative_and_standalone_share_transaction_lock(self):
        comparative=inspect.getsource(savip_book.open_book_position)
        standalone=inspect.getsource(db.commit_savip_single_shadow_entry)
        lock='pg_advisory_xact_lock(734101, 1)'
        self.assertIn(lock,comparative)
        self.assertIn(lock,standalone)
        self.assertIn("WHERE arm='savip_reference' AND status='open'",comparative)
        self.assertIn("WHERE arm='savip_reference' AND status='open'",standalone)

if __name__=="__main__":
    unittest.main()
