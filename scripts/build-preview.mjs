import { mkdir, readFile, writeFile, copyFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';

const out = 'dist/web';
await mkdir(out, { recursive: true });
await copyFile('index.html', out + '/index.html');
for (const name of ['workshop', 'coastal']) {
  const dir = 'artifacts/' + name;
  await mkdir(out + '/' + dir, { recursive: true });
  if (!existsSync(dir + '/review.html')) {
    await writeFile(out + '/' + dir + '/review.html', '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evaluation pending</title><main style="max-width:42rem;margin:12vh auto;padding:1rem;font:18px/1.6 system-ui"><a href="../../index.html">All demos</a><h1>Evaluation pending</h1><p>The completed report will appear here after the results are published.</p></main></html>');
    continue;
  }
  for (const file of ['review.html','report.md','requirements.json','changes.json','usage.json']) {
    await copyFile(dir + '/' + file, out + '/' + dir + '/' + file);
  }
}
