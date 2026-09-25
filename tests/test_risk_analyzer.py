"""
Unit tests for Multi-Factor Risk Analysis.
"""

import unittest
from backend.ml.risk_analyzer import calculate_risk, compute_historical_metrics


class TestRiskAnalyzer(unittest.TestCase):
    def test_low_risk_scenario(self):
        current = {
            "response_time": 150.0,
            "status_code": 200,
            "availability": 1,
            "error_rate": 0.0,
        }
        hist = {
            "avg_response_time": 140.0,
            "std_response_time": 10.0,
            "avg_error_rate": 0.0,
            "availability_rate": 1.0,
        }
        config = {
            "response_time_threshold": 2000.0,
            "error_threshold": 0.05,
        }

        risk = calculate_risk(current, hist, config)
        self.assertIn(risk["risk_level"], ["LOW", "MEDIUM"])
        self.assertLess(risk["risk_score"], 50.0)

    def test_high_risk_outage_scenario(self):
        current = {
            "response_time": 4500.0,
            "status_code": 500,
            "availability": 0,
            "error_rate": 1.0,
        }
        hist = {
            "avg_response_time": 200.0,
            "std_response_time": 20.0,
            "avg_error_rate": 0.01,
            "availability_rate": 0.99,
        }
        config = {
            "response_time_threshold": 2000.0,
            "error_threshold": 0.05,
        }

        risk = calculate_risk(current, hist, config)
        self.assertIn(risk["risk_level"], ["HIGH", "CRITICAL"])
        self.assertGreater(risk["risk_score"], 60.0)


if __name__ == "__main__":
    unittest.main()
