"""Run browser tests against an isolated database, never the working demo."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import HRServer


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='janamen-browser-') as folder:
        server = HRServer(('127.0.0.1', 8008), Path(folder) / 'test.db', root / 'frontend/dist', seed_demo=True)
        print('E2E server: http://127.0.0.1:8008 (temporary database)', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
