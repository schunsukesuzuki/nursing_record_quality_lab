"""Check Compose structure, health semantics and optional inference startup."""
from pathlib import Path
import yaml
root = Path(__file__).resolve().parents[1]
config = yaml.safe_load((root / 'compose.yaml').read_text())
services = config['services']
assert set(services) == {'ollama','model-init','inference','backend','frontend'}
assert '/health/live' in ' '.join(services['inference']['healthcheck']['test'])
assert '/health/ready' not in ' '.join(services['inference']['healthcheck']['test'])
assert 'depends_on' not in services['inference'], 'Inference startup must not depend on model-init.'
assert 'depends_on' not in services['backend'], 'Rule mode must not depend on inference.'
assert services['model-init']['depends_on']['ollama']['condition'] == 'service_healthy'
assert services['model-init']['entrypoint'] == ['/bin/sh', '/opt/model-init.sh']
assert services['model-init']['volumes'] == ['./scripts/model-init.sh:/opt/model-init.sh:ro']
assert 'OLLAMA_HOST' in services['model-init']['environment']
assert (root / 'scripts/model-init.sh').exists()
assert services['frontend']['depends_on']['backend']['condition'] == 'service_healthy'
print('Compose YAML / independence checks OK; services:', ', '.join(sorted(services)))
