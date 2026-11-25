"""Independent CLI checks against completed real artifacts, not the generated eval set."""
import json
import subprocess
import sys
from pathlib import Path

from forgeai.storage import save


def main():
    checks = [
        ('workshop_boundary', 'workshop', 'If I cancel exactly 24 hours before my session, is the booking fee refunded?', 'answered'),
        ('workshop_missing_policy', 'workshop', 'May I bring a guest on Saturday?', 'refused'),
        ('workshop_ambiguous', 'workshop', 'Can I use it?', 'clarify'),
        ('coastal_subtotal', 'coastal', 'What is the item subtotal for three CT-10 probes, excluding tax and shipping?', 'answered'),
    ]
    out = Path('artifacts/cli_checks')
    results = []
    for name, domain, question, expected in checks:
        command = [sys.executable, '-X', 'utf8', '-m', 'forgeai', 'chat', '--agent',
                   f'artifacts/{domain}/agent.json', '--question', question]
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=1200)
        result = {'name': name, 'question': question, 'expected_status': expected,
                  'exit_code': process.returncode, 'stderr': process.stderr, 'command': command}
        try:
            output = json.loads(process.stdout)
            result['execution'] = output
            passed = process.returncode == 0 and output['response']['status'] == expected and not output['guard_errors']
            if name == 'coastal_subtotal':
                values = [t.get('result', {}).get('value') for t in output['tool_results'] if t['name'] == 'calculator']
                passed = passed and 14400 in values and '14400' in output['response']['answer'].replace(',', '')
            if name == 'workshop_boundary':
                text = output['response']['answer'].casefold()
                passed = passed and 'refund' in text and ('yes' in text or 'qualif' in text)
            result['passed'] = passed
        except (ValueError, KeyError) as exc:
            result.update(passed=False, stdout=process.stdout, error=str(exc))
        results.append(result)
        save(out / 'results.json', {'note': 'Hand-written CLI integration probes, separate from generated agent evaluations.',
                                   'checks': results, 'passed': sum(r['passed'] for r in results), 'total': len(results)})
        print(f"{name}: {'PASS' if result['passed'] else 'FAIL'}", flush=True)
    return 0 if all(r['passed'] for r in results) else 2


if __name__ == '__main__':
    raise SystemExit(main())
