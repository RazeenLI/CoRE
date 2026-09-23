from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATASETS = ("Chinook", "MONDIAL", "TPCDS", "Spider")
TARGET_CASES = 100
TARGET_PER_DATASET = 25
SEED = 42
OPERATIONS = ("insert_table", "extend_table", "create_table")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path, limit: int = 3) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(dict(row))
            if len(rows) >= limit:
                break
        return rows


def constraint_body(value: dict[str, Any]) -> dict[str, Any]:
    body = value.get("constraints", value)
    return body if isinstance(body, dict) else {}


def collect_disagreements() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for dataset in DATASETS:
        benchmark_root = ROOT / "data" / dataset / "benchmarks"
        for reference_path in sorted(
            benchmark_root.glob("*/case_*/expected/proposal.json")
        ):
            case_dir = reference_path.parents[1]
            size = reference_path.parents[2].name
            prediction_path = (
                ROOT / "save" / dataset / "standard" / size
                / case_dir.name / "proposal.json"
            )
            if not prediction_path.exists():
                continue
            reference = read_json(reference_path).get("decision")
            prediction = read_json(prediction_path).get("source_decision")
            if reference not in OPERATIONS or prediction not in OPERATIONS:
                continue
            if reference == prediction:
                continue
            result[dataset].append({
                "dataset": dataset,
                "size": size,
                "case": case_dir.name,
                "case_dir": case_dir,
                "reference_decision": reference,
                "predicted_decision": prediction,
                "confusion": f"{reference}->{prediction}",
            })
    return result


def stratified_take(
    candidates: list[dict[str, Any]],
    count: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate["confusion"]].append(candidate)
    for values in groups.values():
        rng.shuffle(values)

    selected: list[dict[str, Any]] = []
    keys = sorted(groups)
    while len(selected) < count and keys:
        next_keys = []
        for key in keys:
            if groups[key] and len(selected) < count:
                selected.append(groups[key].pop())
            if groups[key]:
                next_keys.append(key)
        keys = next_keys

    selected_ids = {(item["dataset"], item["size"], item["case"]) for item in selected}
    remaining = [
        item for item in candidates
        if (item["dataset"], item["size"], item["case"]) not in selected_ids
    ]
    return selected, remaining


def select_cases(
    candidates: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    remaining: dict[str, list[dict[str, Any]]] = {}

    for dataset in DATASETS:
        take = min(TARGET_PER_DATASET, len(candidates.get(dataset, [])))
        chosen, rest = stratified_take(candidates.get(dataset, []), take, rng)
        selected.extend(chosen)
        remaining[dataset] = rest

    while len(selected) < TARGET_CASES:
        progressed = False
        for dataset in DATASETS:
            if remaining[dataset] and len(selected) < TARGET_CASES:
                chosen, rest = stratified_take(remaining[dataset], 1, rng)
                selected.extend(chosen)
                remaining[dataset] = rest
                progressed = True
        if not progressed:
            break

    if len(selected) < TARGET_CASES:
        raise ValueError(
            f"Only {len(selected)} operation disagreements are available; "
            f"{TARGET_CASES} are required."
        )

    rng.shuffle(selected)
    return selected[:TARGET_CASES]


def visible_case(item: dict[str, Any], token: str) -> dict[str, Any]:
    case_dir: Path = item["case_dir"]
    existing_dir = case_dir / "existing"
    incoming_dir = case_dir / "incoming"
    schema = read_json(existing_dir / "schema.json")
    constraints = constraint_body(read_json(existing_dir / "constraints.json"))
    incoming_schema = read_json(incoming_dir / "schema.json")

    existing_rows = {
        table: read_rows(existing_dir / "tables" / f"{table}.csv")
        for table in schema.get("tables", {})
    }
    incoming_tables = incoming_schema.get("tables", {})
    incoming_name = next(iter(incoming_tables), "incoming")

    return {
        "token": token,
        "existing": {
            "tables": schema.get("tables", {}),
            "constraints": {
                "primary_keys": constraints.get("primary_keys", {}),
                "foreign_keys": constraints.get("foreign_keys", {}),
            },
            "rows": existing_rows,
        },
        "incoming": {
            "name": incoming_name,
            "schema": incoming_tables.get(incoming_name, {}),
            "rows": read_rows(incoming_dir / "table.csv"),
        },
    }


def json_for_html(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relational Evolution Annotation</title>
<style>
:root { --ink:#18212d; --muted:#607083; --line:#d9e0e8; --blue:#2563a7; --blue2:#eaf3fc; --bg:#f5f7fa; --card:#fff; --green:#16794b; }
* { box-sizing:border-box; }
body { margin:0; color:var(--ink); background:var(--bg); font:14px/1.42 Arial,sans-serif; }
header { position:sticky; top:0; z-index:20; display:flex; align-items:center; gap:18px; padding:12px 24px; background:#fff; border-bottom:1px solid var(--line); }
header h1 { margin:0; font-size:18px; }
.progress { flex:1; height:8px; border-radius:8px; background:#e7ebf0; overflow:hidden; }
.progress > div { height:100%; background:var(--blue); }
.counter { color:var(--muted); white-space:nowrap; }
main { max-width:1450px; margin:0 auto; padding:22px; }
.intro,.panel,.question { background:var(--card); border:1px solid var(--line); border-radius:10px; box-shadow:0 1px 2px rgba(20,35,55,.04); }
.intro { max-width:760px; margin:40px auto; padding:28px; }
.intro h2 { margin-top:0; }
.intro li { margin:8px 0; }
input[type=text],textarea { width:100%; padding:10px; border:1px solid #b8c3d0; border-radius:6px; font:inherit; }
button { border:0; border-radius:6px; padding:10px 16px; color:#fff; background:var(--blue); cursor:pointer; font-weight:600; }
button.secondary { color:var(--ink); background:#e8edf3; }
button:disabled { opacity:.45; cursor:not-allowed; }
.case-title { display:flex; justify-content:space-between; align-items:end; margin-bottom:12px; }
.case-title h2 { margin:0; }
.layout { display:grid; grid-template-columns:minmax(0,2fr) minmax(300px,1fr); gap:16px; align-items:start; }
.panel { padding:14px; overflow:auto; }
.panel h3 { margin:0 0 10px; font-size:15px; }
.er-svg { width:100%; min-width:680px; height:auto; display:block; background:#fbfcfe; border:1px solid #e4e9ef; border-radius:7px; }
.incoming-name { padding:9px 11px; background:var(--blue2); border-left:4px solid var(--blue); font-weight:700; margin-bottom:10px; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th,td { border:1px solid var(--line); padding:5px 7px; text-align:left; vertical-align:top; overflow-wrap:anywhere; }
th { background:#eef2f6; }
.schema-table td:first-child { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
.badge { display:inline-block; margin-left:4px; padding:0 4px; border-radius:4px; font-size:10px; color:#fff; background:#69798c; }
.badge.pk { background:#996515; }.badge.fk { background:#7a4fa0; }
.samples { margin-top:14px; }
.details { margin-top:16px; }
details { border-top:1px solid var(--line); padding:8px 0; }
summary { cursor:pointer; font-weight:600; }
.question { margin-top:16px; padding:18px; }
.definitions { color:var(--muted); margin:4px 0 14px; }
.choices { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.choice { display:block; padding:14px; border:2px solid var(--line); border-radius:8px; cursor:pointer; }
.choice:has(input:checked) { border-color:var(--blue); background:var(--blue2); }
.choice input { margin-right:7px; }
.choice strong { display:block; margin-bottom:4px; font-size:15px; }
.comment { margin-top:14px; }
.actions { display:flex; justify-content:space-between; gap:10px; margin-top:16px; }
.actions .right { display:flex; gap:10px; }
.saved { color:var(--green); font-weight:600; margin-left:8px; }
.hidden { display:none !important; }
@media(max-width:900px){ .layout{grid-template-columns:1fr}.choices{grid-template-columns:1fr} main{padding:12px} }
</style>
</head>
<body>
<header id="topbar" class="hidden">
  <h1>Evolution Annotation</h1>
  <div class="progress"><div id="progressFill"></div></div>
  <div class="counter" id="counter"></div>
  <button class="secondary" id="exportTop">Export JSON</button>
</header>
<main>
  <section class="intro" id="intro">
    <h2>Incoming-table-driven evolution annotation</h2>
    <p>For each case, inspect the existing relational database and the incoming table. Select <strong>every operation that you consider reasonable</strong>. More than one operation may be selected.</p>
    <ul>
      <li><strong>Insert</strong>: the incoming rows belong to an existing relation without requiring new attributes.</li>
      <li><strong>Extend</strong>: an existing relation should gain one or more attributes represented by the incoming table.</li>
      <li><strong>Create</strong>: the incoming table represents a distinct relation that should be added to the database.</li>
    </ul>
    <p>Use only the information shown. There is no need to design column mappings or constraints.</p>
    <label><strong>Annotator ID</strong></label>
    <input id="annotatorId" type="text" autocomplete="off" placeholder="e.g., A01">
    <div style="margin-top:16px"><button id="start">Start / Resume</button></div>
  </section>
  <section id="caseView" class="hidden"></section>
</main>
<script>
const MANIFEST_ID = __MANIFEST_ID__;
const CASES = __CASES__;
const OPS = ["insert_table","extend_table","create_table"];
const LABELS = {insert_table:"Insert",extend_table:"Extend",create_table:"Create"};
let annotator = "";
let state = {index:0,responses:{}};

function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function key(){return `core-operation-audit:${MANIFEST_ID}:${annotator}`;}
function save(){localStorage.setItem(key(),JSON.stringify(state));}
function load(){const raw=localStorage.getItem(key()); if(raw){try{state=JSON.parse(raw)}catch(_){}}}

function constraintMaps(c){
  const pk=c.primary_keys||{}, fk=c.foreign_keys||{}, fkCols={};
  Object.entries(fk).forEach(([t,items])=>(items||[]).forEach(x=>(x.columns||[]).forEach(col=>{(fkCols[t]??=new Set()).add(col)})));
  return {pk,fk,fkCols};
}

function makeER(data){
  const tables=data.tables||{}, names=Object.keys(tables), maps=constraintMaps(data.constraints||{});
  const cols=Math.min(4,Math.max(1,Math.ceil(Math.sqrt(names.length))));
  const cellW=260, gapY=34, positions={}, rowHeights=[];
  for(let i=0;i<names.length;i++){
    const r=Math.floor(i/cols), h=42+18*(tables[names[i]].column_order||Object.keys(tables[names[i]].columns||{})).length;
    rowHeights[r]=Math.max(rowHeights[r]||0,h);
  }
  const rowY=[]; let y=24; rowHeights.forEach((h,i)=>{rowY[i]=y;y+=h+gapY});
  names.forEach((name,i)=>{const r=Math.floor(i/cols),c=i%cols;positions[name]={x:20+c*cellW,y:rowY[r],w:225,h:rowHeights[r]-4}});
  const width=40+cols*cellW, height=Math.max(150,y);
  let edges="";
  Object.entries(maps.fk).forEach(([from,items])=>(items||[]).forEach(fk=>{
    const a=positions[from],b=positions[fk.referenced_table]; if(!a||!b)return;
    const x1=a.x+a.w/2,y1=a.y+a.h/2,x2=b.x+b.w/2,y2=b.y+b.h/2;
    edges+=`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#8794a5" stroke-width="1.5" marker-end="url(#arrow)"/>`;
  }));
  let nodes="";
  names.forEach(name=>{
    const p=positions[name], table=tables[name], order=table.column_order||Object.keys(table.columns||{});
    nodes+=`<g><rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="6" fill="#fff" stroke="#9eabb9"/><rect x="${p.x}" y="${p.y}" width="${p.w}" height="28" rx="6" fill="#dbe9f6"/><text x="${p.x+9}" y="${p.y+19}" font-size="13" font-weight="700">${esc(name)}</text>`;
    order.forEach((col,j)=>{
      const meta=(table.columns||{})[col]||{}, tags=[];
      if((maps.pk[name]||[]).includes(col))tags.push("PK"); if(maps.fkCols[name]?.has(col))tags.push("FK");
      const suffix=tags.length?` [${tags.join(",")}]`:"";
      nodes+=`<text x="${p.x+9}" y="${p.y+47+j*18}" font-size="11" font-family="monospace">${esc(col)} : ${esc(meta.type||meta.type_raw||"unknown")}${suffix}</text>`;
    }); nodes+="</g>";
  });
  return `<svg class="er-svg" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#8794a5"/></marker></defs>${edges}${nodes}</svg>`;
}

function schemaTable(schema,pk=[],fk=[]){
  const columns=schema.columns||{}, order=schema.column_order||Object.keys(columns);
  return `<table class="schema-table"><thead><tr><th>Column</th><th>Type</th><th>Nullable</th></tr></thead><tbody>${order.map(name=>{const c=columns[name]||{};return `<tr><td>${esc(name)}${pk.includes(name)?'<span class="badge pk">PK</span>':''}${fk.includes(name)?'<span class="badge fk">FK</span>':''}</td><td>${esc(c.type_raw||c.type||"unknown")}</td><td>${c.nullable===false?"No":"Yes"}</td></tr>`}).join("")}</tbody></table>`;
}
function rowsTable(rows){
  if(!rows?.length)return '<p class="definitions">No sampled rows available.</p>';
  const columns=Object.keys(rows[0]);
  return `<table><thead><tr>${columns.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(c=>`<td>${esc(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function existingDetails(existing){
  const maps=constraintMaps(existing.constraints||{});
  return Object.entries(existing.tables||{}).map(([name,schema])=>{
    const fks=maps.fkCols[name]?Array.from(maps.fkCols[name]):[];
    return `<details><summary>${esc(name)}</summary>${schemaTable(schema,maps.pk[name]||[],fks)}<div class="samples"><strong>Sample rows</strong>${rowsTable(existing.rows[name]||[])}</div></details>`;
  }).join("");
}

function render(){
  const item=CASES[state.index], response=state.responses[item.token]||{selected_operations:[],comment:"",duration_seconds:0};
  response.opened_at=response.opened_at||Date.now(); state.responses[item.token]=response; save();
  document.getElementById("counter").textContent=`Case ${state.index+1} / ${CASES.length}`;
  document.getElementById("progressFill").style.width=`${100*(state.index+1)/CASES.length}%`;
  document.getElementById("caseView").innerHTML=`
    <div class="case-title"><h2>Case ${String(state.index+1).padStart(3,"0")}</h2><span class="saved">Autosaved locally</span></div>
    <div class="layout">
      <section class="panel"><h3>Existing relational database</h3>${makeER(item.existing)}<div class="details"><strong>Table details and sampled rows</strong>${existingDetails(item.existing)}</div></section>
      <section class="panel"><h3>Incoming table</h3><div class="incoming-name">${esc(item.incoming.name)}</div>${schemaTable(item.incoming.schema)}<div class="samples"><strong>Sample rows</strong>${rowsTable(item.incoming.rows)}</div></section>
    </div>
    <section class="question">
      <h3>Which evolution operations are reasonable?</h3>
      <p class="definitions">Select every operation that could reasonably incorporate this incoming table into the existing RDB.</p>
      <div class="choices">
        ${OPS.map(op=>`<label class="choice"><strong><input type="checkbox" data-op="${op}" ${response.selected_operations.includes(op)?"checked":""}>${LABELS[op]}</strong><span>${op==="insert_table"?"The rows belong to an existing relation without new attributes.":op==="extend_table"?"An existing relation should gain attributes from the incoming table.":"The incoming table should become a distinct relation."}</span></label>`).join("")}
      </div>
      <div class="comment"><label><strong>Optional comment</strong></label><textarea id="comment" rows="2" placeholder="Brief reason or uncertainty">${esc(response.comment||"")}</textarea></div>
      <div class="actions"><button class="secondary" id="prev" ${state.index===0?"disabled":""}>Previous</button><div class="right"><button class="secondary" id="export">Export JSON</button><button id="next" ${response.selected_operations.length?"":"disabled"}>${state.index===CASES.length-1?"Save & Finish":"Save & Next"}</button></div></div>
    </section>`;
  document.querySelectorAll("[data-op]").forEach(input=>input.addEventListener("change",updateResponse));
  document.getElementById("comment").addEventListener("input",updateResponse);
  document.getElementById("prev").onclick=()=>{updateResponse();state.index--;save();render();window.scrollTo(0,0)};
  document.getElementById("next").onclick=()=>{updateResponse();if(state.index<CASES.length-1){state.index++;save();render();window.scrollTo(0,0)}else{save();exportData();alert("All cases are saved. Please send the exported JSON file to the study organizer.")}};
  document.getElementById("export").onclick=exportData;
}
function updateResponse(){
  const item=CASES[state.index],r=state.responses[item.token];
  r.selected_operations=Array.from(document.querySelectorAll("[data-op]:checked")).map(x=>x.dataset.op);
  r.comment=document.getElementById("comment")?.value||"";
  r.duration_seconds=Math.round(((r.duration_seconds||0)+(Date.now()-(r.opened_at||Date.now()))/1000)*10)/10;
  r.opened_at=Date.now(); save();
  const next=document.getElementById("next");if(next)next.disabled=!r.selected_operations.length;
}
function exportData(){
  updateResponse();
  const payload={study:"operation-validity-audit",manifest_id:MANIFEST_ID,annotator_id:annotator,exported_at:new Date().toISOString(),responses:CASES.map(c=>({case_token:c.token,...(state.responses[c.token]||{selected_operations:[],comment:"",duration_seconds:0})})).map(r=>{delete r.opened_at;return r})};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}),a=document.createElement("a");
  a.href=URL.createObjectURL(blob);a.download=`operation_annotations_${annotator}_${MANIFEST_ID.slice(0,8)}.json`;a.click();URL.revokeObjectURL(a.href);
}
document.getElementById("start").onclick=()=>{
  annotator=document.getElementById("annotatorId").value.trim();if(!annotator){alert("Please enter an annotator ID.");return}
  load();document.getElementById("intro").classList.add("hidden");document.getElementById("caseView").classList.remove("hidden");document.getElementById("topbar").classList.remove("hidden");render();
};
document.getElementById("exportTop").onclick=()=>exportData();
</script>
</body>
</html>'''


def main() -> None:
    candidates = collect_disagreements()
    selected = select_cases(candidates)
    public_cases = []
    manifest_cases = []

    for index, item in enumerate(selected, start=1):
        token = f"AV{index:03d}"
        public_cases.append(visible_case(item, token))
        manifest_cases.append({
            "case_token": token,
            "dataset": item["dataset"],
            "size": item["size"],
            "case": item["case"],
            "reference_decision": item["reference_decision"],
            "predicted_decision": item["predicted_decision"],
            "confusion": item["confusion"],
        })

    identity = json.dumps(manifest_cases, sort_keys=True).encode("utf-8")
    manifest_id = hashlib.sha256(identity).hexdigest()[:16]
    manifest = {
        "manifest_id": manifest_id,
        "seed": SEED,
        "selection": "operation disagreements, confusion-stratified",
        "cases": manifest_cases,
    }
    (HERE / "selected_cases.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rendered = HTML_TEMPLATE.replace(
        "__MANIFEST_ID__", json_for_html(manifest_id)
    ).replace("__CASES__", json_for_html(public_cases))
    (HERE / "annotation.html").write_text(rendered, encoding="utf-8")

    counts: dict[str, int] = defaultdict(int)
    for case in manifest_cases:
        counts[case["dataset"]] += 1
    print(f"manifest_id: {manifest_id}")
    print(f"cases:       {len(manifest_cases)}")
    print(f"datasets:    {dict(counts)}")
    print(f"html:        {HERE / 'annotation.html'}")


if __name__ == "__main__":
    main()
