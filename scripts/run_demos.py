"""Run the two demonstrations sequentially against the same local inference service."""
from pathlib import Path
import argparse
from forgeai.factory import build
from forgeai.model import LocalModel
from forgeai.runtime import keep_awake
from forgeai.recovery import RecoveryModel


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='runs', help='Parent output directory; existing runs are never overwritten')
    parser.add_argument('--recover-workshop', help='Interrupted workshop run with an exact reusable inference prefix')
    args = parser.parse_args()
    outcomes = []
    for name in ('workshop', 'coastal'):
        print(f'\n=== {name.upper()} DEMONSTRATION ===', flush=True)
        folder = Path('examples') / name
        model = RecoveryModel(args.recover_workshop) if name == 'workshop' and args.recover_workshop else LocalModel()
        state = build(model, (folder / 'brief.txt').read_text(encoding='utf-8'),
                      folder / 'docs', Path(args.out) / name)
        outcomes.append(state['status'])
    return 0 if all(s == 'completed' for s in outcomes) else 2


def main():
    with keep_awake():
        return run()


if __name__ == '__main__':
    raise SystemExit(main())
