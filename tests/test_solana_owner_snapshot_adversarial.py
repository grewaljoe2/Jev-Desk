"""Synthetic adversarial Solana owner-map release-gate tests.

These tests demonstrate invalid evidence; they do not certify a verifier.
Run: python -m unittest discover -s tests -p 'test_solana_owner_snapshot_adversarial.py'
"""
import unittest


class OwnerSnapshotAdversarialTests(unittest.TestCase):
    def test_mixed_slot_false_concentration(self):
        before = {"A": {"alice": 50}, "B": {"bob": 50}}
        after = {"A": {"bob": 50}, "B": {"alice": 50}}
        stitched = [before["A"], after["B"]]
        totals = {}
        for account in stitched:
            for owner, amount in account.items():
                totals[owner] = totals.get(owner, 0) + amount
        self.assertEqual(sum(totals.values()), 100)
        self.assertEqual(max(totals.values()), 100)
        self.assertEqual(max(sum(v.get(o, 0) for v in before.values()) for o in ("alice", "bob")), 50)
        self.assertEqual(max(sum(v.get(o, 0) for v in after.values()) for o in ("alice", "bob")), 50)

    def test_identical_repeated_scans_do_not_certify_snapshot(self):
        stitched = (("A", "alice", 50), ("B", "alice", 50))
        self.assertEqual(stitched, tuple(stitched))
        self.assertEqual(sum(a for _, _, a in stitched), 100)
        self.assertEqual(len({owner for _, owner, _ in stitched}), 1)

    def test_filtered_delta_omits_closed_account(self):
        indexed = {"A": ("alice", 50), "B": ("bob", 50)}
        mint_filtered_changes = {"B": ("bob", 100)}
        indexed.update(mint_filtered_changes)
        self.assertIn("A", indexed)
        self.assertEqual(sum(amount for _, amount in indexed.values()), 150)

    def test_supply_conservation_cannot_prove_owners(self):
        correct = {"alice": 50, "bob": 50}
        false = {"alice": 100}
        self.assertEqual(sum(correct.values()), sum(false.values()))
        self.assertNotEqual(max(correct.values()), max(false.values()))

    def test_zero_balance_accounts_are_not_holders(self):
        balances = {"alice": 0, "bob": 10, "carol": 0}
        self.assertEqual(sum(v > 0 for v in balances.values()), 1)

    def test_account_concentration_only_lower_bounds_owner_concentration(self):
        accounts = {"A": ("alice", 30), "B": ("alice", 30), "C": ("bob", 40)}
        account_top = max(amount for _, amount in accounts.values())
        owners = {}
        for owner, amount in accounts.values():
            owners[owner] = owners.get(owner, 0) + amount
        self.assertEqual(account_top, 40)
        self.assertEqual(max(owners.values()), 60)


if __name__ == "__main__":
    unittest.main()
