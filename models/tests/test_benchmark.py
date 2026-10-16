import unittest

from models.benchmark.run import can_spend, estimate_cost, recommend


class BenchmarkTests(unittest.TestCase):
    def test_estimate_cost_uses_token_prices(self):
        self.assertEqual(estimate_cost(1_000_000, 1_000_000, 1.0, 2.0), 3.0)

    def test_budget_cap_blocks_expensive_request(self):
        self.assertTrue(can_spend(1.99, 0.01, 2.0))
        self.assertFalse(can_spend(1.99, 0.02, 2.0))

    def test_recommend_prefers_valid_lower_cost_model(self):
        rows = [{"model": "a", "valid": True, "estimated_cost": 0.10, "latency_ms": 200}, {"model": "b", "valid": True, "estimated_cost": 0.20, "latency_ms": 100}, {"model": "c", "valid": False, "estimated_cost": 0.01, "latency_ms": 50}]
        self.assertEqual(recommend(rows)["primary"], "a")
