"""Combined artifact/transport checks. No browser automation is used here."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import HRServer

ROOT = Path(__file__).resolve().parents[1]


class CombinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / "frontend/dist/index.html").exists():
            raise unittest.SkipTest("Build frontend before running combined checks")
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = HRServer(("127.0.0.1", 0), Path(cls.temp.name) / "combined.db", ROOT / "frontend/dist", seed_demo=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def test_static_headers_assets_and_spa_fallback(self):
        # Check serving of our built files, without rendering/observing a browser page.
        for path in ("/", "/requests", "/academy/1", "/assistant", "/branches", "/integrations"):
            with urllib.request.urlopen(self.base + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("text/html", response.headers["Content-Type"])
                self.assertEqual(int(response.headers["Content-Length"]), (ROOT / "frontend/dist/index.html").stat().st_size)
        for asset in (ROOT / "frontend/dist/assets").iterdir():
            with urllib.request.urlopen(self.base + "/assets/" + asset.name, timeout=5) as response:
                self.assertEqual(response.status, 200)
                if asset.suffix == ".js":
                    self.assertIn("javascript", response.headers["Content-Type"])
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.base + "/%2e%2e/%2e%2e/server.py", timeout=5)
        self.assertEqual(error.exception.code, 404)

    def test_typescript_client_against_real_api(self):
        node = os.getenv("NODE_BINARY") or shutil.which("node")
        if not node or not (ROOT / "frontend/node_modules/esbuild").exists():
            self.skipTest("Node and npm ci are required for the optional frontend client test")

        # Verify that esbuild platform binary actually executes in this environment
        probe = subprocess.run(
            [node, "-e", "import('esbuild').then(m => m.build({stdin: {contents: 'export const x = 1'}, write: false})).catch(e => { console.error(e.message); process.exit(42); })"],
            cwd=ROOT / "frontend", capture_output=True, text=True, encoding="utf-8", timeout=15
        )
        if probe.returncode != 0:
            err = probe.stderr.strip() or probe.stdout.strip()
            self.skipTest(f"esbuild binary is not executable in this OS environment ({err}). Run 'cd frontend && npm ci' to install native binaries.")

        completed = subprocess.run([node, str(ROOT / "tests/frontend-client.mjs"), self.base], cwd=ROOT,
                                   capture_output=True, text=True, encoding="utf-8", timeout=90)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Frontend API integration: OK", completed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
