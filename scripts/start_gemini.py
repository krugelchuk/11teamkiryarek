"""Explicit Gemini launcher. The only required setting is the user's API key."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / 'data/gemini.json'


def configure(path=CONFIG, replace=False):
    stored = {}
    if path.exists() and not replace:
        try:
            if path.stat().st_size > 16384:
                raise ValueError()
            stored = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(stored, dict):
                raise ValueError()
        except (ValueError, OSError):
            raise ValueError('Cannot read Gemini settings. Run with --new-key.') from None
    key = os.getenv('GEMINI_API_KEY', '').strip() or (stored.get('api_key', '') if not replace else '')
    if not key:
        key = getpass.getpass('Gemini API key (hidden input): ').strip()
        if not key or not key.isascii() or any(c.isspace() for c in key) or len(key) > 512:
            raise ValueError('Invalid or empty API key.')
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps({'api_key': key, 'model': 'auto'}), encoding='utf-8')
        os.chmod(temp, 0o600)
        temp.replace(path)
    if not isinstance(key, str) or not key.isascii() or not key:
        raise ValueError('Invalid API key settings. Run with --new-key.')
    os.environ['JANAMEN_AI_PROVIDER'] = 'gemini'
    os.environ['GEMINI_API_KEY'] = key
    os.environ['GEMINI_MODEL'] = os.getenv('GEMINI_MODEL', '').strip() or str(stored.get('model') or 'auto')
    os.environ.setdefault('JANAMEN_AI_TIMEOUT', '20')


def main():
    parser = argparse.ArgumentParser(description='Qadam11 + Gemini: enter your key once')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--new-key', action='store_true')
    parser.add_argument('--check', action='store_true', help='Run live AI verification and exit')
    args = parser.parse_args()
    try:
        configure(replace=args.new_key)
    except (ValueError, OSError, EOFError, KeyboardInterrupt) as exc:
        # Never include parsed provider content or secret settings in error messages.
        print('Gemini configuration failed. Check data/gemini.json or run with --new-key.')
        return 1
    if args.check:
        from scripts.ai_smoke_test import run_smoke_test
        return run_smoke_test()
    from app.model import gemini_model, ProviderUnavailable
    try:
        selected = gemini_model(os.environ['GEMINI_API_KEY'], os.environ['GEMINI_MODEL'])
        os.environ['GEMINI_MODEL'] = selected
        print('Gemini model selected: ' + selected)
        print('Connection to the model is verified when you ask AI Jana a question.')
    except ProviderUnavailable:
        print('Gemini model list unavailable. AI Jana will use local search until the service is available.')
    if args.demo:
        from scripts.prepare_demo import prepare
        prepare(ROOT / 'data/demo.db')
    from server import main as serve
    sys.argv = [sys.argv[0]] + (['--db', str(ROOT / 'data/demo.db')] if args.demo else [])
    serve()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
