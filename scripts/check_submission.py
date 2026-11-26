"""Check saved evidence, run the real CLI probes, and export offline review pages."""
import json
import subprocess
import sys

from scripts.export_review import export
from scripts.verify_artifacts import verify
from forgeai.runtime import keep_awake
from forgeai.storage import save


def main():
    evidence = [verify('artifacts/' + name) for name in ('workshop', 'coastal')]
    print(json.dumps(evidence, indent=2), flush=True)
    checks = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'scripts.smoke_agents'])
    for name in ('workshop', 'coastal'):
        export('artifacts/' + name)
    save('artifacts/verification.json', {
        'artifact_checks': evidence,
        'cli_checks_exit_code': checks.returncode,
        'note': 'Structural artifact checks and four independent CLI probes; not proof of semantic correctness or submission readiness.'
    })
    return checks.returncode


if __name__ == '__main__':
    with keep_awake():
        raise SystemExit(main())
