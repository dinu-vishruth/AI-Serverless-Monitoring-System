import unittest
from unittest.mock import patch

from backend.database import dynamodb


class TestDynamoDBConfiguration(unittest.TestCase):
    @patch("backend.database.dynamodb.HAS_BOTO3", True)
    @patch("backend.database.dynamodb.get_settings")
    def test_development_environment_does_not_require_aws_credentials(self, get_settings):
        get_settings.return_value.environment = "development"

        self.assertIsNone(dynamodb.get_dynamodb_resource())


if __name__ == "__main__":
    unittest.main()