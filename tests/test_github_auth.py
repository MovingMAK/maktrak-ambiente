import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "maktrak_setup.py"
SPEC = importlib.util.spec_from_file_location("maktrak_setup", MODULE_PATH)
maktrak_setup = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(maktrak_setup)


class GithubAuthTests(unittest.TestCase):
    def test_read_github_credentials_from_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / ".git-credentials"
            store_path.write_text("https://octocat:secret-token@github.com\n", encoding="utf-8")
            credentials = maktrak_setup.read_github_credentials_from_store(store_path)
            self.assertEqual(credentials, ("octocat", "secret-token"))

    def test_configure_git_credential_helper(self):
        result = maktrak_setup.configure_git_credential_helper()
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
