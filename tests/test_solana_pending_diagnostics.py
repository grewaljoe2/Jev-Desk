"""Check that incomplete owner evidence is a pending condition, not a failed trade."""
import unittest
from pathlib import Path

class SolanaPendingDiagnosticTests(unittest.TestCase):
    def test_pending_owner_evidence_is_not_labeled_error(self):
        src=Path("app/research/savip_chain_worker.py").read_text()
        self.assertIn('"pending_unverified" in str(e) else "error"',src)
        self.assertIn('raise RuntimeError("solana_wallet_check_pending_unverified: "+evidence_status[:80])',src)

if __name__=="__main__":
    unittest.main()
