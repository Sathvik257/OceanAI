"""Export completed run evidence as a self-contained, offline HTML review page."""
import json
import sys
from pathlib import Path

from forgeai.storage import read

HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ForgeAI evidence review</title>
<style>
:root{font-family:system-ui,sans-serif;color:#172c37;background:#f4f5f1;font-size:15px}*{box-sizing:border-box}body{margin:0}header{background:#163b42;color:#fff;padding:28px max(24px,calc((100vw - 1200px)/2))}header small{letter-spacing:.14em;text-transform:uppercase;color:#acd8cf}h1{font-size:32px;margin:8px 0}header p{color:#d5e4e3;max-width:800px;line-height:1.5}main{max-width:1248px;margin:auto;padding:24px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{background:white;border:1px solid #dbe2dc;border-radius:8px;padding:18px}.metric strong{display:block;font-size:28px;margin:8px 0}.muted{color:#566c72}.note{line-height:1.6;background:#e8eee9;border-left:4px solid #557d62;padding:14px 18px;margin:20px 0}.bar{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:24px 0 16px}select,input,button{font:inherit}select,button{padding:8px 12px;border:1px solid #a9bcb8;border-radius:5px;background:white;color:#173a40}button{cursor:pointer}button:hover{background:#edf4ef}button:focus-visible,select:focus-visible{outline:3px solid #b88025;outline-offset:2px}.layout{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(400px,1.3fr);gap:20px}.cases{display:flex;flex-direction:column;gap:8px;max-height:70vh;overflow:auto}.case{text-align:left;padding:14px;border:1px solid #d6ded8;line-height:1.45}.case.active{border:2px solid #286e62;padding:13px}.tag{display:inline-block;font-size:12px;font-weight:700;border-radius:3px;padding:3px 7px;margin-right:8px}.pass{background:#e0efe3;color:#235a37}.fail{background:#f9e3dc;color:#8c3529}.case p{margin:8px 0 0}.detail{background:white;border:1px solid #d6ded8;border-radius:8px;padding:24px;min-width:0}.detail h2{font-size:21px;line-height:1.4}.detail h3{font-size:14px;text-transform:uppercase;letter-spacing:.04em;margin-top:24px}.prose{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}blockquote{border-left:3px solid #a6c4b7;margin:12px 0;padding:8px 14px;background:#f3f6f2;line-height:1.6;overflow-wrap:anywhere}code{font-size:12px;background:#edf0ec;padding:2px 5px}.facts{padding-left:20px;line-height:1.7}.facts li{margin-bottom:12px}footer{border-top:1px solid #d0dbd3;padding:24px;color:#52666c;line-height:1.6}dialog{max-width:850px;width:90%;max-height:85vh;border:1px solid #9badab;border-radius:8px;padding:24px}dialog::backdrop{background:#0e2428aa}.empty{padding:24px}.sr{position:absolute;left:-9999px}@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.cases{max-height:40vh}header{padding:24px}h1{font-size:27px}main{padding:16px}}@media print{.bar,.cases,dialog{display:none}.layout{display:block}.detail{border:none}.metrics{grid-template-columns:repeat(4,1fr)}header{background:white;color:#173a40}header small,header p{color:#173a40}}
</style>
<header><small>ForgeAI / Evidence review</small><h1 id="title"></h1><p>A generated agent, its tests, and the evidence behind its scores. Every result below comes from the saved local run.</p></header>
<main><section class="metrics" id="metrics" aria-label="Run summary"></section>
<div class="note" id="limits"></div><div class="bar"><label>Evaluation <select id="version"></select></label><label><input id="failed" type="checkbox"> Show failures only</label><span id="count" class="muted" aria-live="polite"></span></div>
<div class="layout"><nav class="cases" id="cases" aria-label="Evaluation cases"></nav><article class="detail" id="detail" aria-live="polite"></article></div>
<section class="note"><strong>Groundability gaps</strong><ul id="gaps"></ul><strong>Attached tools</strong><p id="tools"></p></section>
<footer>This is an offline evidence viewer, not a live chatbot or an independent benchmark. Generated questions and model judgments can be wrong. Inspect the quotations and reasoning yourself. The six holdout cases were not used to select patches. See <a href="report.md">the quality report</a>, <a href="requirements.json">requirements</a>, <a href="changes.json">repair history</a> and <a href="usage.json">resource usage</a>.</footer></main>
<dialog id="source"><button id="close">Close source</button><h2 id="sourceTitle"></h2><div class="prose" id="sourceText"></div></dialog>
<script id="payload" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('payload').textContent), $=id=>document.getElementById(id);
const casesById=Object.fromEntries(data.evals.cases.map(c=>[c.id,c]));
const chunkById=Object.fromEntries(data.corpus.chunks.map(c=>[c.id,c]));
const node=(tag,text,cls)=>{const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e};
const score=s=>`${s.passed}/${s.total}`;
$('title').textContent=data.agent.name;
const selected=data.cards.find(c=>c.version===data.state.selected_version), hold=data.cards.find(c=>c.version==='holdout');
for(const [label,value,caption] of [['Development',score(selected.summary),'Selected version '+data.state.selected_version],['Holdout',score(hold.summary),'Evaluated once after selection'],['Generated tests',data.evals.cases.length,'Quoted facts checked against sources'],['Local model',data.usage.model.replace('qwen3-',''),'Open weights, recorded inference']]){const e=node('div','', 'metric');e.append(node('span',label,'muted'),node('strong',value),node('small',caption,'muted'));$('metrics').append(e)}
$('limits').textContent='Completed run. These small, model-generated samples do not establish production accuracy. Citation checks verify quote occurrence; semantic correctness still depends on an imperfect model judge.';
for(const card of data.cards){const o=node('option',card.version==='holdout'?'Holdout — final agent':`Version ${card.version} — ${score(card.summary)} passed`);o.value=String(card.version);$('version').append(o)}
$('version').value=String(data.state.selected_version);
for(const gap of data.agent.requirements.gaps)$('gaps').append(node('li',gap));
if(!data.agent.requirements.gaps.length)$('gaps').append(node('li','No gaps flagged by the factory; this is not proof of complete coverage.'));
$('tools').textContent=data.agent.tools.length?data.agent.tools.join(', '):'None';
function sourceButton(id){const c=chunkById[id], b=node('button',c?`${c.source} · ${c.locator}`:id);b.onclick=()=>{$('sourceTitle').textContent=c?`${c.source} · ${c.locator}`:id;$('sourceText').textContent=c?c.text:'Source unavailable';$('source').showModal()};return b}
function show(s){const c=casesById[s.case_id], d=$('detail');d.replaceChildren();const badge=node('span',s.passed?'PASS':'FAIL','tag '+(s.passed?'pass':'fail'));d.append(badge,node('code',`${s.case_id} · ${c.kind} · ${c.split}`),node('h2',c.question));
const x=s.execution,r=x?.response;d.append(node('h3','Expected behavior'),node('p',c.expected_status),node('h3','Actual response'),node('p',r?`${r.status}: ${r.answer}`:s.evaluation_error||'No response','prose'));
d.append(node('h3','Judge verdict'),node('p',`Correct: ${s.judge.correct} · Grounded: ${s.judge.grounded} · Behavior: ${s.judge.behavior}`),node('p',s.judge.reason,'prose'));
if(!s.passed)d.append(node('p','Failure category: '+s.category));
d.append(node('h3','Expected source facts'));
if(!c.facts.length)d.append(node('p','No factual answer expected; this case tests refusal or clarification.','muted'));
for(const fact of c.facts)d.append(sourceButton(fact.chunk_id),node('blockquote',fact.quote));
d.append(node('h3','Evidence cited by the agent'));
for(const e of r?.evidence||[])d.append(sourceButton(e.chunk_id),node('blockquote',e.quote));
if(!(r?.evidence||[]).length)d.append(node('p','No quotations cited.','muted'));
if(x?.guard_errors?.length){d.append(node('h3','Runtime guard failures'),node('p',x.guard_errors.join('\n'),'prose'),node('h3','Raw response before guard'),node('p',JSON.stringify(x.raw_response,null,2),'prose'))}
if(x?.tool_results?.length)d.append(node('h3','Tool trace'),node('pre',JSON.stringify(x.tool_results,null,2),'prose'));
d.append(node('h3','Retrieval diagnostic'),node('p',`Expected chunk IDs retrieved: ${s.retrieval_hit}. This is diagnostic; overlapping chunks can contain the same fact.`,'muted'));
for(const b of $('cases').children)b.classList.toggle('active',b.dataset.id===s.case_id)}
function render(){const card=data.cards.find(c=>String(c.version)===$('version').value), rows=card.cases.filter(s=>!$('failed').checked||!s.passed);$('cases').replaceChildren();$('count').textContent=`${rows.length} of ${card.cases.length} cases shown`;for(const s of rows){const b=node('button','', 'case');b.dataset.id=s.case_id;b.append(node('span',s.passed?'PASS':'FAIL','tag '+(s.passed?'pass':'fail')),node('code',s.case_id),node('p',casesById[s.case_id].question));b.onclick=()=>show(s);$('cases').append(b)}if(rows.length)show(rows[0]);else $('detail').replaceChildren(node('p','No failures in this evaluation. This does not imply perfect reliability.','empty'))}
$('version').onchange=render;$('failed').onchange=render;$('close').onclick=()=>$('source').close();render();
</script></html>'''


def export(folder):
    root = Path(folder)
    state = read(root / 'state.json')
    if state['status'] != 'completed':
        raise ValueError('Only completed runs may be exported as a completed evidence review')
    data = {name: read(root / filename) for name, filename in
            [('agent', 'agent.json'), ('evals', 'evals.json'), ('corpus', 'corpus.json'), ('usage', 'usage.json')]}
    data['state'] = state
    data['cards'] = [{'version': v['version'], **read(root / f"scorecard.v{v['version']}.json")}
                     for v in read(root / 'iterations.json')]
    data['cards'].append({'version': 'holdout', **read(root / 'scorecard.holdout.json')})
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    target = root / 'review.html'
    target.write_text(HTML.replace('__DATA__', payload), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    for folder in sys.argv[1:] or ['artifacts/workshop', 'artifacts/coastal']:
        export(folder)
