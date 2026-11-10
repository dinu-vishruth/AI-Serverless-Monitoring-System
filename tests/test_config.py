import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.utils.config import Settings


class TestSettings(unittest.TestCase):
    def test_env_file_path_is_independent_of_working_directory(self):
        env_file = Path(Settings.model_config["env_file"])

        self.assertTrue(env_file.is_absolute())
        self.assertEqual(env_file.name, ".env")
        self.assertEqual(env_file.parent, Path(__file__).resolve().parents[1])

    def test_empty_environment_key_does_not_override_dotenv(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("GROQ_API_KEY=test-groq-key\n", encoding="utf-8")

            with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
                settings = Settings(_env_file=env_file)

        self.assertEqual(settings.groq_api_key, "test-groq-key")
