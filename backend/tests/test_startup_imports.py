"""Basic API startup must work without importing the inference runtime."""

import os
from pathlib import Path
import subprocess
import sys


def test_api_starts_without_loading_torch_or_forecast_model():
    result = subprocess.run(
        [sys.executable, "-c", """
import importlib.abc
import sys

class NoInferenceAtStartup(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'torch' or fullname.startswith('torch.'):
            raise AssertionError('Startup attempted to import PyTorch')

sys.meta_path.insert(0, NoInferenceAtStartup())
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
assert client.get('/api/v1/health').json()['status'] == 'ok'
assert '/api/forecast/approaches' in app.openapi()['paths']
assert 'torch' not in sys.modules
assert 'app.services.forecast_service' not in sys.modules
print('STARTUP_OK')
"""],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "SMARTTWIN_DECISION_ENGINE": "rule-based"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "STARTUP_OK" in result.stdout
