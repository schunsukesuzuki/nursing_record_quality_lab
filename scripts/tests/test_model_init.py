"""Execute the real init shell with a stub Ollama CLI to test control flow."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'model-init.sh'
STUB = '''#!/bin/sh
case "$1" in
  show)
    test -e "$MODEL_PRESENT_FILE" ;;
  pull)
    printf '%s\\n' "$2" >> "$MODEL_PULL_LOG"
    if [ "${MODEL_PULL_FAIL:-0}" = 1 ]; then exit 23; fi
    touch "$MODEL_PRESENT_FILE" ;;
  *)
    echo "unknown ollama command $1" >&2
    exit 11 ;;
esac
'''

class ModelInitTests(unittest.TestCase):
    def call_script(self, *, model_exists=False, pull_fails=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            stub = bin_dir / 'ollama'
            stub.write_text(STUB)
            stub.chmod(0o755)
            model = root / 'model_present'
            pulls = root / 'pulls.log'
            if model_exists:
                model.touch()
            env = {**os.environ,
                   'PATH': f'{bin_dir}:{os.environ.get("PATH", "")}',
                   'OLLAMA_HOST': 'http://ollama:11434',
                   'MODEL_NAME': 'qwen3:0.6b',
                   'MODEL_PRESENT_FILE': str(model),
                   'MODEL_PULL_LOG': str(pulls),
                   'MODEL_PULL_FAIL': '1' if pull_fails else '0'}
            result = subprocess.run(['sh', str(SCRIPT)], env=env,
                                    capture_output=True, text=True, timeout=10)
            return result, pulls.read_text() if pulls.exists() else None, model.exists()

    def test_skips_pull_if_present(self):
        result, calls, model = self.call_script(model_exists=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(calls)
        self.assertTrue(model)
        self.assertIn('skipping download', result.stdout)

    def test_download_if_missing(self):
        result, calls, model = self.call_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, 'qwen3:0.6b\n')
        self.assertTrue(model)
        self.assertIn('verified successfully', result.stdout)

    def test_failure_does_not_report_success(self):
        result, calls, model = self.call_script(pull_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, 'qwen3:0.6b\n')
        self.assertFalse(model)
        self.assertIn('download failed', result.stderr)

if __name__ == '__main__':
    unittest.main()
