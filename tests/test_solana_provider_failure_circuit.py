import unittest
from pathlib import Path

class SolanaProviderFailureCircuitTests(unittest.TestCase):
    def test_infrastructure_failure_uses_long_cooldown(self):
        src=Path("app/research/savip_chain_worker.py").read_text()
        self.assertIn('cooldown=3600.0 if any(x in reason_text for x in infrastructure)',src)
        for category in ("rate_limited","response_too_large","snapshot_slot_mismatch",
                         "independent_confirmation_unavailable"):
            self.assertIn('"'+category+'"',src)
        self.assertIn('self._recent_tokens[row["token_id"]]=time.monotonic()+cooldown',src)

if __name__=="__main__":
    unittest.main()
