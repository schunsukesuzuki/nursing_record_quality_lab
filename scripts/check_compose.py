"""Validate YAML syntax without needing the Docker daemon."""
from pathlib import Path
import yaml
root=Path(__file__).resolve().parents[1]
config=yaml.safe_load((root/'compose.yaml').read_text())
services = set(config['services'])
assert services == {'ollama','model-init','inference','backend','frontend'}
print('Compose YAML syntax OK; services:', ', '.join(sorted(services)))
