"""Small-corpus ingestion and BM25 retrieval, without an embedding service."""
import csv
import math
import re
from collections import Counter
from pathlib import Path

from .storage import digest

SUPPORTED = {'.pdf', '.txt', '.md', '.csv'}
STOP = set('a an the is are was were be to of and or in on at for with what which how do does can i me my it this that please tell about'.split())


def tokens(text):
    return [w for w in re.findall(r'[\w]+', text.casefold()) if w not in STOP]


def ingest(folder, chunk_words=180, overlap=30):
    root = Path(folder).resolve()
    if not root.is_dir():
        raise ValueError(f'Document directory does not exist: {root}')
    if not 40 <= chunk_words <= 500 or not 0 <= overlap < chunk_words:
        raise ValueError('Invalid chunking parameters')
    chunks, manifest, warnings = [], [], []
    files = sorted(p for p in root.rglob('*') if p.is_file())
    if len(files) > 200:
        raise ValueError('At most 200 files are supported per run')
    for path in files:
        if not path.resolve().is_relative_to(root):
            raise ValueError('Document symlinks outside the corpus are not allowed')
        name = path.relative_to(root).as_posix()
        if path.suffix.lower() not in SUPPORTED:
            warnings.append(f'Ignored unsupported file: {name}')
            continue
        if path.stat().st_size > 20_000_000:
            raise ValueError(f'File exceeds 20 MB: {name}')
        manifest.append({'source': name, 'sha256': digest(path.read_bytes())})
        if path.suffix.lower() == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ValueError(f'Encrypted PDF is unsupported: {name}')
            units = [(f'page {i+1}', p.extract_text() or '') for i, p in enumerate(reader.pages)]
        elif path.suffix.lower() == '.csv':
            with path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            units = [(f'row {i+2}', '; '.join(f'{k}: {v}' for k, v in row.items())) for i, row in enumerate(rows)]
        else:
            text = path.read_text(encoding='utf-8-sig')
            units = [('text', text)]
        count_before = len(chunks)
        for locator, text in units:
            words = text.split()
            if not words:
                warnings.append(f'No extractable text: {name}, {locator}; OCR is not provided')
            for start in range(0, len(words), chunk_words - overlap):
                content = ' '.join(words[start:start+chunk_words])
                identity = f'{name}|{locator}|{start}|{content}'
                chunks.append({'id': digest(identity)[:16], 'source': name, 'locator': locator,
                               'text': content, 'start_word': start})
                if start + chunk_words >= len(words):
                    break
        if len(chunks) == count_before:
            raise ValueError(f'No readable content in {name}; supply text or an OCRed PDF')
    if not chunks:
        raise ValueError('No supported, nonempty documents found')
    if sum(len(c['text']) for c in chunks) > 1_000_000:
        raise ValueError('Corpus exceeds the 1 MB extracted-text limit for this prototype')
    return {'chunks': chunks, 'manifest': manifest, 'warnings': warnings,
            'chunking': {'words': chunk_words, 'overlap': overlap}}


def retrieve(chunks, question, top_k=3, diversify=False):
    query = tokens(question)
    counts = [Counter(tokens(c['text'] + ' ' + c['source'])) for c in chunks]
    lengths = [sum(c.values()) for c in counts]
    avg = sum(lengths) / max(1, len(lengths))
    df = Counter(t for c in counts for t in c)
    ranked = []
    for chunk, count, length in zip(chunks, counts, lengths):
        score = 0.0
        for term in query:
            freq = count[term]
            idf = math.log(1 + (len(chunks) - df[term] + .5) / (df[term] + .5))
            score += idf * freq * 2.2 / (freq + 1.2 * (.25 + .75 * length / max(avg, 1)))
        if score > 0:
            ranked.append({**chunk, 'score': round(score, 5)})
    ranked.sort(key=lambda c: (-c['score'], c['id']))
    if diversify:
        unique, others, seen = [], [], set()
        for c in ranked:
            (others if c['source'] in seen else unique).append(c)
            seen.add(c['source'])
        ranked = unique + others
    return ranked[:top_k]
