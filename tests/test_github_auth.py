import importlib.util
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote


MODULE_PATH = Path(__file__).resolve().parents[1] / "maktrak_setup.py"
SPEC = importlib.util.spec_from_file_location("maktrak_setup", MODULE_PATH)
maktrak_setup = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(maktrak_setup)


class GithubAuthTests(unittest.TestCase):
    def test_write_git_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / ".git-credentials"
            maktrak_setup._write_git_credentials("octocat", "secret-token", store_path)
            self.assertTrue(store_path.exists())
            content = store_path.read_text(encoding="utf-8")
            expected_user = quote("octocat")
            expected_token = quote("secret-token")
            self.assertIn(f"https://{expected_user}:{expected_token}@github.com", content)
            self.assertEqual(store_path.stat().st_mode & 0o777, 0o600)

    def test_validate_git(self):
        """Git deve estar disponivel no PATH (instalado no sistema)."""
        result = maktrak_setup._validate_git()
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
