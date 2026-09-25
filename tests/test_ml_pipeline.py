"""
Unit tests for Machine Learning Anomaly Detection pipeline.
"""

import unittest
from backend.ml.preprocessing import (
    records_to_dataframe,
    add_derived_features,
    extract_features,
    prepare_single_record,
    normalize_status_code,
)
from backend.ml.train import train_model
from backend.ml.predict import predict_anomaly


class TestMLPipeline(unittest.TestCase):
    def setUp(self):
        self.service_id = "test-service-123"
        self.normal_records = [
            {
                "service_id": self.service_id,
                "timestamp": f"2026-09-25T10:{i:02d}:00Z",
                "response_time": 100.0 + (i % 5) * 5.0,
                "status_code": 200,
                "error_rate": 0.0,
                "availability": 1,
                "timeout": 0,
                "request_success": 1,
            }
            for i in range(25)
        ]

    def test_feature_extraction(self):
        df = records_to_dataframe(self.normal_records)
        df = add_derived_features(df)
        features = extract_features(df)
        self.assertEqual(len(features), 25)
        self.assertGreater(features.shape[1], 5)

        single_feat = prepare_single_record(self.normal_records[-1], self.normal_records[:-1])
        self.assertEqual(single_feat.shape[0], 1)

    def test_status_code_normalization(self):
        self.assertEqual(normalize_status_code(200), 0.0)
        self.assertEqual(normalize_status_code(404), 0.5)
        self.assertEqual(normalize_status_code(500), 1.0)

    def test_train_and_predict(self):
        # 1. Train model
        train_result = train_model(self.service_id, self.normal_records)
        self.assertIn(train_result["status"], ["trained", "success", "insufficient_data"])

        # 2. Predict on normal record
        normal_prediction = predict_anomaly(
            self.service_id,
            self.normal_records[-1],
            self.normal_records[-10:],
        )
        self.assertIn("anomaly_score", normal_prediction)
        self.assertIn("anomaly", normal_prediction)

        # 3. Predict on severe anomaly
        anomalous_record = {
            "service_id": self.service_id,
            "timestamp": "2026-09-25T10:30:00Z",
            "response_time": 9500.0,
            "status_code": 500,
            "error_rate": 1.0,
            "availability": 0,
            "timeout": 1,
            "request_success": 0,
        }
        anomaly_prediction = predict_anomaly(
            self.service_id,
            anomalous_record,
            self.normal_records[-10:],
        )
        self.assertIn("anomaly_score", anomaly_prediction)


if __name__ == "__main__":
    unittest.main()
