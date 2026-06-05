"""
可视化生成器 —— 把 Pipeline 结果变成可交互的 Dashboard。

用法：
    # 从 JSON 文件生成
    python visualize.py result.json
    
    # 运行 Pipeline 后直接打开
    python visualize.py --run "查询文本"
    
    # 在代码里调用
    from visualize import generate_dashboard, open_dashboard
    html = generate_dashboard(result_dict)
    open_dashboard(html)
"""

from __future__ import annotations
import json
import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional


def _build_dag_data(result: dict) -> dict:
    """
    把 pipeline.run() 的结果转成 dashboard 需要的格式。
    如果 result 里没有 nodes/edges，从 dag_stats 补全。
    """
    data = {
        "dag_stats": result.get("dag_stats", {}),
        "iterations": result.get("iterations", 0),
        "token_summary": result.get("token_summary", {}),
        "duration_s": result.get("duration_s", 0),
        "stop_reason": result.get("stop_reason", ""),
        "final_answer": result.get("final_answer", ""),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", {}),
    }
    
    # 如果没有 nodes，从 dag_stats 生成占位
    if not data["nodes"] and data["dag_stats"]:
        stats = data["dag_stats"]
        for i in range(stats.get("total", 0)):
            data["nodes"].append({
                "id": f"task_{i+1}",
                "question": f"任务 {i+1}",
                "agent_type": "builder",
                "status": "completed" if i < stats.get("completed", 0) else "pending",
                "result": "",
                "duration_s": 0,
                "tokens_used": 0,
                "priority": 5,
                "dependencies": [],
                "completeness_score": 0.0,
            })
    
    return data


def generate_dashboard(result: dict, output_path: str = "dashboard.html") -> str:
    """
    生成 dashboard HTML 文件。
    
    Args:
        result: pipeline.run() 返回的字典
        output_path: 输出路径
    
    Returns:
        生成的 HTML 文件绝对路径
    """
    data = _build_dag_data(result)
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    data_json = data_json.replace("</script", "<\\/script")
    
    html = _TEMPLATE.replace("{{DAG_DATA_PLACEHOLDER}}", data_json)
    
    output = Path(output_path)
    output.write_text(html, encoding="utf-8")
    return str(output.resolve())


def open_dashboard(html_path: str):
    """在默认浏览器中打开 dashboard"""
    url = "file://" + os.path.abspath(html_path)
    webbrowser.open(url)
    print(f"📊 Dashboard 已打开: {url}")


def run_and_visualize(query: str, output_path: str = "dashboard.html", **kwargs):
    """运行 Pipeline 并生成可视化"""
    from pipeline import DynamicPipeline
    from llm_client import call_llm

    llm_fn = lambda sys, user: call_llm(system_prompt=sys, user_prompt=user)
    pipeline = DynamicPipeline(llm_fn=llm_fn, **kwargs)
    result = pipeline.run(query)
    
    # 补充 nodes 和 edges（pipeline 原始输出不包含这些）
    # 从 dag 中提取
    path = generate_dashboard(result, output_path)
    open_dashboard(path)
    return result


# ─── 主入口 ───

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python visualize.py result.json       # 从 JSON 生成")
        print("  python visualize.py --run '查询文本'    # 运行 Pipeline 并生成")
        sys.exit(1)
    
    if sys.argv[1] == "--run" and len(sys.argv) > 2:
        query = sys.argv[2]
        run_and_visualize(query)
    else:
        json_path = sys.argv[1]
        with open(json_path, encoding="utf-8") as f:
            result = json.load(f)
        html = generate_dashboard(result)
        open_dashboard(html)


# ─── Dashboard HTML 模板 ───

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>oh-my-Dynamic Dashboard</title>
<style>
:root {
  --bg: #f5f7fa;
  --card: #ffffff;
  --text: #1a1a2e;
  --text2: #6b7280;
  --accent: #6366f1;
  --green: #10b981;
  --yellow: #f59e0b;
  --red: #ef4444;
  --gray: #9ca3af;
  --blue: #3b82f6;
  --radius: 12px;
  --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--text); padding:24px; }

.header { text-align:center; margin-bottom:24px; }
.header h1 { font-size:24px; font-weight:700; color:var(--text); }
.header p { color:var(--text2); margin-top:4px; font-size:14px; }

.grid { display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:16px; margin-bottom:24px; }
.stat-card { background:var(--card); border-radius:var(--radius); padding:20px; box-shadow:var(--shadow); }
.stat-card .label { font-size:12px; color:var(--text2); text-transform:uppercase; letter-spacing:0.5px; }
.stat-card .value { font-size:28px; font-weight:700; margin-top:4px; }
.stat-card .sub { font-size:12px; color:var(--text2); margin-top:2px; }

.progress-bar { height:6px; background:#e5e7eb; border-radius:3px; margin-top:8px; overflow:hidden; }
.progress-bar .fill { height:100%; border-radius:3px; transition:width 0.5s; }

.main-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.card { background:var(--card); border-radius:var(--radius); padding:20px; box-shadow:var(--shadow); }
.card h2 { font-size:16px; font-weight:600; margin-bottom:12px; display:flex; align-items:center; gap:8px; }
.card h2 .badge { font-size:11px; padding:2px 8px; border-radius:99px; background:#eef2ff; color:var(--accent); font-weight:500; }

/* DAG Graph */
.dag-container { position:relative; min-height:300px; }
.dag-layer { display:flex; justify-content:center; gap:16px; margin-bottom:24px; }
.dag-node { 
  width:180px; padding:12px 16px; border-radius:10px; border:2px solid #e5e7eb;
  cursor:pointer; transition:all 0.2s; position:relative;
}
.dag-node:hover { transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,0.1); }
.dag-node.completed { border-color:var(--green); background:#f0fdf4; }
.dag-node.running { border-color:var(--yellow); background:#fffbeb; }
.dag-node.failed { border-color:var(--red); background:#fef2f2; }
.dag-node.pending { border-color:var(--gray); background:#f9fafb; }
.dag-node .q { font-size:13px; font-weight:500; line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.dag-node .meta { font-size:11px; color:var(--text2); margin-top:6px; display:flex; justify-content:space-between; }
.dag-node .type { font-size:10px; padding:1px 6px; border-radius:4px; background:#eef2ff; color:var(--accent); }

/* Timeline */
.timeline-item { display:flex; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid #f3f4f6; }
.timeline-item:last-child { border:none; }
.timeline-bar { height:24px; border-radius:6px; min-width:20px; position:relative; }
.timeline-bar .dur { position:absolute; right:8px; top:50%; transform:translateY(-50%); font-size:11px; color:white; font-weight:500; white-space:nowrap; }
.timeline-label { font-size:13px; min-width:120px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* Result viewer */
.result-panel { max-height:300px; overflow-y:auto; }
.result-item { padding:12px; background:#f9fafb; border-radius:8px; margin-bottom:8px; cursor:pointer; }
.result-item:hover { background:#f3f4f6; }
.result-item .rq { font-size:13px; font-weight:500; }
.result-item .rr { font-size:12px; color:var(--text2); margin-top:4px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }

/* Stop conditions */
.cond-item { display:flex; align-items:center; gap:8px; padding:8px 0; border-bottom:1px solid #f3f4f6; }
.cond-item:last-child { border:none; }
.cond-dot { width:8px; height:8px; border-radius:50%; }
.cond-dot.active { background:var(--green); }
.cond-dot.triggered { background:var(--red); animation:pulse 1s infinite; }
.cond-dot.inactive { background:#d1d5db; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Modal */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.3); z-index:100; justify-content:center; align-items:center; }
.modal-overlay.show { display:flex; }
.modal { background:white; border-radius:16px; padding:24px; max-width:600px; width:90%; max-height:80vh; overflow-y:auto; box-shadow:0 20px 60px rgba(0,0,0,0.15); }
.modal h3 { font-size:16px; margin-bottom:12px; }
.modal .close { float:right; cursor:pointer; font-size:20px; color:var(--text2); }
.modal pre { background:#f3f4f6; padding:12px; border-radius:8px; font-size:13px; white-space:pre-wrap; word-break:break-all; }
</style>
</head>
<body>

<div class="header">
  <h1>🚀 oh-my-Dynamic</h1>
  <p>多智能体编排 Dashboard</p>
</div>

<div class="grid" id="stats"></div>

<div class="main-grid">
  <div class="card">
    <h2>🗺️ DAG 任务图 <span class="badge" id="dag-badge"></span></h2>
    <div class="dag-container" id="dag-graph"></div>
  </div>

  <div class="card">
    <h2>⏱️ 执行时间线</h2>
    <div id="timeline"></div>
  </div>

  <div class="card">
    <h2>📄 结果列表</h2>
    <div class="result-panel" id="results"></div>
  </div>

  <div class="card">
    <h2>🛑 停机条件</h2>
    <div id="conditions"></div>
    <div style="margin-top:16px; padding:12px; background:#f0fdf4; border-radius:8px;" id="final-answer">
      <div style="font-size:12px; color:var(--text2); margin-bottom:4px;">最终答案</div>
      <div style="font-size:13px; line-height:1.5;" id="answer-text"></div>
    </div>
  </div>
</div>

<div class="modal-overlay" id="modal">
  <div class="modal">
    <span class="close" onclick="document.getElementById('modal').classList.remove('show')">×</span>
    <h3 id="modal-title"></h3>
    <pre id="modal-body"></pre>
  </div>
</div>

<script>
const DATA = {{DAG_DATA_PLACEHOLDER}};

// HTML 转义函数，防止 XSS 注入
function esc(s) { const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML; }

// Stats
const stats = DATA.dag_stats;
const tokens = DATA.token_summary;
const dur = DATA.duration_s;

document.getElementById('stats').innerHTML = `
  <div class="stat-card">
    <div class="label">任务完成</div>
    <div class="value" style="color:var(--green)">${stats.completed||0}/${stats.total||0}</div>
    <div class="progress-bar"><div class="fill" style="width:${((stats.completed||0)/(stats.total||1)*100)}%;background:var(--green)"></div></div>
  </div>
  <div class="stat-card">
    <div class="label">Token 使用</div>
    <div class="value" style="color:var(--blue)">${(tokens.total||0).toLocaleString()}</div>
    <div class="sub">${(tokens.percent_used||0).toFixed(1)}% 已用 · ${tokens.call_count||0} 次调用</div>
    <div class="progress-bar"><div class="fill" style="width:${tokens.percent_used||0}%;background:var(--blue)"></div></div>
  </div>
  <div class="stat-card">
    <div class="label">执行耗时</div>
    <div class="value">${dur<60?dur.toFixed(0)+'s':(dur/60).toFixed(1)+'m'}</div>
    <div class="sub">${DATA.iterations||0} 次迭代</div>
  </div>
  <div class="stat-card">
    <div class="label">完备度</div>
    <div class="value" style="color:var(--accent)">${((stats.avg_score||stats.completeness||0)*100).toFixed(0)}%</div>
    <div class="sub">停机: ${esc(DATA.stop_reason||'-')}</div>
  </div>
`;

// DAG Badge
document.getElementById('dag-badge').textContent = `${(stats.completed||0)}/${(stats.total||0)}`;

// DAG Graph — group by dependencies depth
const nodes = DATA.nodes || [];
const edges = DATA.edges || {};

// Compute layers
const depth = {};
const inDeg = {};
nodes.forEach(n => { depth[n.id] = 0; inDeg[n.id] = 0; });
nodes.forEach(n => {
  (n.dependencies||[]).forEach(d => { inDeg[n.id] = (inDeg[n.id]||0)+1; });
  Object.keys(edges).forEach(k => {
    (edges[k]||[]).forEach(c => { if(c===n.id) inDeg[n.id]=(inDeg[n.id]||0)+1; });
  });
});

// BFS to assign depth
const queue = nodes.filter(n => !(n.dependencies||[]).length).map(n=>n.id);
const visited = new Set();
while(queue.length) {
  const id = queue.shift();
  if(visited.has(id)) continue;
  visited.add(id);
  const deps = (nodes.find(n=>n.id===id)?.dependencies)||[];
  depth[id] = deps.length ? Math.max(...deps.map(d=>depth[d]||0))+1 : 0;
  Object.keys(edges).forEach(k => {
    if((edges[k]||[]).includes(id)) {
      depth[k] = Math.max(depth[k]||0, (depth[id]||0)+1);
      queue.push(k);
    }
  });
}

const maxDepth = Math.max(...Object.values(depth), 0);
const layers = {};
nodes.forEach(n => {
  const d = depth[n.id]||0;
  if(!layers[d]) layers[d] = [];
  layers[d].push(n);
});

let dagHTML = '';
for(let i=0; i<=maxDepth; i++) {
  const layer = layers[i] || [];
  dagHTML += `<div class="dag-layer">`;
  layer.forEach(n => {
    const statusCls = n.status || 'pending';
    const typeColor = {builder:'#3b82f6',explorer:'#8b5cf6',reviewer:'#f59e0b'}[n.agent_type]||'#6b7280';
    dagHTML += `<div class="dag-node ${statusCls}" onclick="showDetail('${n.id}')">
      <div class="q">${esc(n.question||n.id)}</div>
      <div class="meta">
        <span class="type" style="background:${typeColor}20;color:${typeColor}">${esc(n.agent_type||'task')}</span>
        <span>${n.duration_s?n.duration_s.toFixed(0)+'s':''}</span>
      </div>
    </div>`;
  });
  dagHTML += `</div>`;
}
document.getElementById('dag-graph').innerHTML = dagHTML || '<p style="color:var(--text2)">无 DAG 数据</p>';

// Timeline
const typeColors = {builder:'#3b82f6',explorer:'#8b5cf6',reviewer:'#f59e0b'};
const maxDur = Math.max(...nodes.map(n=>n.duration_s||0), 1);
let timelineHTML = '';
nodes.filter(n=>n.duration_s).forEach(n => {
  const w = ((n.duration_s||0)/maxDur*70+10).toFixed(0);
  const c = typeColors[n.agent_type]||'#6b7280';
  timelineHTML += `<div class="timeline-item">
    <span class="timeline-label">${esc((n.question||n.id).substring(0,15))}</span>
    <div class="timeline-bar" style="width:${w}%;background:${c}"><span class="dur">${(n.duration_s||0).toFixed(0)}s</span></div>
  </div>`;
});
document.getElementById('timeline').innerHTML = timelineHTML || '<p style="color:var(--text2)">无时间线数据</p>';

// Results
let resultsHTML = '';
nodes.filter(n=>n.status==='completed'&&n.result).forEach(n => {
  resultsHTML += `<div class="result-item" onclick="showResult('${n.id}')">
    <div class="rq">${esc((n.question||'').substring(0,50))}</div>
    <div class="rr">${esc((n.result||'').substring(0,100))}</div>
  </div>`;
});
document.getElementById('results').innerHTML = resultsHTML || '<p style="color:var(--text2)">无结果</p>';

// Answer
document.getElementById('answer-text').textContent = (DATA.final_answer||'暂无').substring(0,500);

// Stop conditions
const conds = [
  {name:'ReadyForSynthesis', desc:`完备度 ≥ 80%`, active: (stats.completeness||0)>=0.8},
  {name:'HighConfidence', desc:`置信度 ≥ 75% 且完成 ≥ 50%`, active: (stats.avg_score||0)>=0.75},
  {name:'DiminishingReturns', desc:`改善 < 5%`, active: false},
  {name:'TokenBudget', desc:`Token < 预算`, active: (tokens.percent_used||0)<100},
  {name:'MaxIterations', desc:`迭代 < 上限`, active: true},
];
const triggered = DATA.stop_reason || '';
let condsHTML = '';
conds.forEach(c => {
  const isTriggered = triggered.includes(c.name);
  const cls = isTriggered ? 'triggered' : (c.active ? 'active' : 'inactive');
  condsHTML += `<div class="cond-item"><div class="cond-dot ${cls}"></div><span style="font-size:13px;font-weight:${isTriggered?600:400}">${c.name}</span><span style="font-size:12px;color:var(--text2);margin-left:auto">${c.desc}</span></div>`;
});
document.getElementById('conditions').innerHTML = condsHTML;

// Detail modal
function showDetail(id) {
  const n = nodes.find(x=>x.id===id);
  if(!n) return;
  document.getElementById('modal-title').textContent = n.question || id;
  document.getElementById('modal-body').textContent = JSON.stringify(n, null, 2);
  document.getElementById('modal').classList.add('show');
}
function showResult(id) {
  const n = nodes.find(x=>x.id===id);
  if(!n) return;
  document.getElementById('modal-title').textContent = n.question || id;
  document.getElementById('modal-body').textContent = n.result || '无结果';
  document.getElementById('modal').classList.add('show');
}
document.getElementById('modal').addEventListener('click', function(e) {
  if(e.target===this) this.classList.remove('show');
});
</script>
</body>
</html>
"""
