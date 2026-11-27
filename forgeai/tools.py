"""Read-only tools. Definitions never grant arbitrary Python, files or URLs."""
import ast
import csv
import math
import operator
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = {
    'csv_lookup': 'Exact lookup of a column value in a supplied CSV catalogue. Arguments: source, column, value.',
    'calculator': 'Arithmetic for requested quantities, totals or conversions. Argument: expression. No Python execution.',
    'current_date': 'Current UTC date only, when the brief requires live date awareness. No arguments.',
}


def calculator(expression):
    if not isinstance(expression, str) or len(expression) > 150:
        raise ValueError('Expression must be a string of at most 150 characters')
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
    tree = ast.parse(expression, mode='eval')
    if len(list(ast.walk(tree))) > 40:
        raise ValueError('Expression too complex')

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in ops:
            value = ops[type(node.op)](evaluate(node.left), evaluate(node.right))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        else:
            raise ValueError('Only numeric literals and + - * / are supported')
        if not math.isfinite(value) or abs(value) > 1e12:
            raise ValueError('Result outside safe numeric range')
        return value
    return evaluate(tree.body)


def execute(name, args, allowed, corpus_root):
    if name not in allowed or name not in REGISTRY:
        raise ValueError(f'Tool is not attached: {name}')
    if name == 'calculator':
        return {'expression': args['expression'], 'value': calculator(args['expression'])}
    if name == 'current_date':
        return {'date': datetime.now(timezone.utc).date().isoformat(), 'timezone': 'UTC'}
    root = Path(corpus_root).resolve()
    requested_source = args.get('source')
    if requested_source:
        source = (root / requested_source).resolve()
        source_resolution = 'explicit'
    else:
        candidates = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.csv']
        if len(candidates) != 1:
            raise ValueError('Specify source: the corpus does not contain exactly one CSV')
        source = candidates[0].resolve()
        source_resolution = 'only_csv_in_corpus'
    if not source.is_relative_to(root) or source.suffix.lower() != '.csv':
        raise ValueError('CSV source must be inside the packaged corpus')
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if args['column'] not in (reader.fieldnames or []):
            raise ValueError('Unknown CSV column')
        rows = [row for row in reader if str(row[args['column']]).casefold() == str(args['value']).casefold()]
    return {'source': source.relative_to(root).as_posix(), 'source_resolution': source_resolution,
            'rows': rows[:20], 'total_matches': len(rows)}
