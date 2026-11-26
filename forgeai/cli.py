import argparse
import json
import sys
from pathlib import Path

from .agent import Agent
from .factory import build
from .model import LocalModel
from .runtime import keep_awake
from .recovery import RecoveryModel


def run(argv=None):
    parser = argparse.ArgumentParser(description='ForgeAI: build and test an agent from a brief and documents')
    sub = parser.add_subparsers(dest='command', required=True)
    factory = sub.add_parser('build', help='Run the unattended factory (or --interactive intake)')
    factory.add_argument('--brief', required=True, help='UTF-8 text file containing the brief')
    factory.add_argument('--docs', required=True)
    factory.add_argument('--out', required=True)
    factory.add_argument('--interactive', action='store_true')
    factory.add_argument('--recover-from', help='Replay an exact audited request prefix from an interrupted run into a new output directory')
    factory.add_argument('--iterations', type=int, default=3, choices=(1, 2, 3))
    chat = sub.add_parser('chat', help='Load any generated definition and ask questions')
    chat.add_argument('--agent', required=True)
    chat.add_argument('--question', help='Single question; omit for a dialogue')
    for cmd in (factory, chat):
        cmd.add_argument('--endpoint', default='http://127.0.0.1:8080/v1', help='llama.cpp /v1 or Ollama base URL')
        cmd.add_argument('--model', default='qwen3-4b-instruct-2507')
        cmd.add_argument('--token-budget', type=int, default=300000)
        cmd.add_argument('--seconds', type=int, default=10800)
        cmd.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args(argv)
    model = LocalModel(args.endpoint, args.model, max_tokens=args.token_budget, seconds=args.seconds, timeout=args.timeout)
    try:
        if args.command == 'build':
            if args.recover_from:
                model = RecoveryModel(args.recover_from, endpoint=args.endpoint, model=args.model,
                                      max_tokens=args.token_budget, seconds=args.seconds, timeout=args.timeout)
            state = build(model, Path(args.brief).read_text(encoding='utf-8'), args.docs, args.out, args.interactive, args.iterations)
            return 0 if state['status'] == 'completed' else 2
        agent = Agent.load(args.agent, model)
        if args.question:
            print(json.dumps(agent.answer(args.question), indent=2, ensure_ascii=False))
        else:
            print(f"{agent.definition['name']} | /quit to exit. Each question is independent.")
            while True:
                question = input('\nYou> ').strip()
                if question.lower() in {'/quit', '/exit'}:
                    break
                if question:
                    result = agent.answer(question)
                    print(json.dumps(result['response'], indent=2, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, OSError, EOFError) as exc:
        print(f'ForgeAI: {exc}', file=sys.stderr)
        return 2


def main(argv=None):
    with keep_awake():
        return run(argv)


if __name__ == '__main__':
    sys.exit(main())
