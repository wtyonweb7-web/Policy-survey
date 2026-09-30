"""
政府AI政策收集工具 - 自包含HTML生成器
从数据库读取数据，生成一个独立的HTML文件，无需服务端即可浏览搜索
"""
import json
import os
from datetime import datetime, timedelta
from models import get_db
from config import ACTIVE_DAYS

OUTPUT_FILE = "政策报告.html"
CRAWL_LOG_FILE = "crawl_log.json"


def load_crawl_log():
    """加载最近一次爬取的过程日志（若存在）"""
    if not os.path.exists(CRAWL_LOG_FILE):
        return {"generated_at": "", "recent_week_start": "", "entries": [], "errors": []}
    try:
        with open(CRAWL_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"generated_at": "", "recent_week_start": "", "entries": [], "errors": []}


def load_policies():
    """从数据库加载政策数据（同一标题只取来源最权威/评分最高的一条）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM policies
        WHERE is_ai_related = 1
        ORDER BY publish_date DESC, ai_score DESC
    """).fetchall()

    # 同时获取非AI的（用于统计和上下文）
    total = conn.execute("SELECT COUNT(*) as c FROM policies").fetchone()["c"]
    active = conn.execute("SELECT COUNT(*) as c FROM policies WHERE is_archived = 0 AND is_ai_related = 1").fetchone()["c"]

    # 按标题去重：同标题保留第一条（已按ai_score DESC排序，即保留评分最高的来源）
    seen_titles = set()
    policies = []
    sources = set()
    types = set()
    regions = set()
    for r in rows:
        d = dict(r)
        title = d.get("title", "").strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)
        policies.append(d)
        if d.get("source"):
            sources.add(d["source"])
        if d.get("article_type"):
            types.add(d["article_type"])
        if d.get("region"):
            regions.add(d["region"])

    ai_count = len(policies)

    conn.close()
    return {
        "policies": policies,
        "stats": {
            "total": total,
            "ai_related": ai_count,
            "active": active,
            "sources": sorted(sources),
            "types": sorted(types),
            "regions": sorted(regions),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    }


def html_escape(text):
    if not text:
        return ""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;")
            .replace("'", "&#39;"))


def generate_html(data, crawl_log=None):
    """生成自包含HTML"""
    policies = data["policies"]
    stats = data["stats"]
    crawl_log = crawl_log or {"generated_at": "", "recent_week_start": "", "entries": [], "errors": []}

    data_json = json.dumps(policies, ensure_ascii=False)
    sources_json = json.dumps(stats["sources"], ensure_ascii=False)
    types_json = json.dumps(stats["types"], ensure_ascii=False)
    regions_json = json.dumps(stats["regions"], ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI政策收集 - {stats['generated_at'][:10]}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#1d2129;font-size:14px;line-height:1.6;padding:0}}
.app{{max-width:1100px;margin:0 auto;padding:16px 20px 40px}}

.header{{display:flex;justify-content:space-between;align-items:center;padding:16px 0;border-bottom:1px solid #e5e6e8;margin-bottom:16px;flex-wrap:wrap;gap:8px}}
.header-left h1{{font-size:22px;font-weight:600}}
.header-left .sub{{font-size:13px;color:#86909c}}
.header-right{{font-size:12px;color:#86909c}}

.stats-bar{{display:flex;gap:4px;margin-bottom:16px;background:#fff;border-radius:8px;padding:12px 20px;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
.stat-item{{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px}}
.stat-label{{font-size:12px;color:#86909c}}
.stat-value{{font-size:22px;font-weight:600;color:#1d2129}}

.filter-bar{{background:#fff;border-radius:8px;padding:10px 16px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
.filter-row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.search-box{{flex:1;min-width:200px}}
.search-box input{{width:100%;padding:7px 12px;border:1px solid #d9dde2;border-radius:6px;font-size:13px;outline:0}}
.search-box input:focus{{border-color:#165dff;box-shadow:0 0 0 2px rgba(22,93,255,.15)}}
.filter-group{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.filter-group select{{padding:6px 10px;border:1px solid #d9dde2;border-radius:6px;font-size:13px;background:#fff;cursor:pointer;outline:0}}
.toggle-label{{display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px;color:#4e5969;user-select:none}}

.result-info{{padding:8px 4px;font-size:13px;color:#4e5969;margin-bottom:8px}}

.policy-list{{display:flex;flex-direction:column;gap:8px}}

.policy-card{{background:#fff;border-radius:8px;padding:16px 20px;box-shadow:0 1px 2px rgba(0,0,0,.06);cursor:pointer;transition:box-shadow .2s}}
.policy-card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.1)}}
.card-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:6px}}
.card-title{{font-size:15px;font-weight:500;color:#1d2129;line-height:1.5;flex:1}}
.card-badges{{display:flex;gap:4px;flex-shrink:0;flex-wrap:wrap}}
.badge{{font-size:11px;padding:1px 8px;border-radius:4px;font-weight:500;white-space:nowrap}}
.badge-ai{{background:#e8f4ff;color:#165dff}}
.badge-high{{background:#ffe8ba;color:#b47d00}}
.badge-type{{background:#f0f5f0;color:#1e8b4c}}
.badge-archived{{background:#f0f0f5;color:#86909c}}

.card-meta{{display:flex;gap:16px;font-size:12px;color:#86909c;margin-bottom:4px;flex-wrap:wrap}}
.card-keywords{{margin-bottom:6px;display:flex;gap:4px;flex-wrap:wrap}}
.kw-tag{{font-size:11px;padding:1px 6px;border-radius:3px;background:#f0f5ff;color:#165dff;border:1px solid #d6e4ff}}

.card-summary{{font-size:13px;color:#4e5969;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:6px;line-height:1.7}}
.tag{{font-size:11px;padding:1px 8px;border-radius:4px;background:#f0f5ff;color:#165dff;border:1px solid #d6e4ff}}
.tag-limit{{background:#fff0f0;color:#cc2020;border-color:#ffd4d4}}

mark{{background:#fff3b0;padding:0 2px;border-radius:2px;font-style:normal}}

.card-detail{{margin-top:12px;padding-top:12px;border-top:1px solid #eaecef;display:none}}
.card-detail.open{{display:block}}
.detail-section{{margin-bottom:10px}}
.detail-label{{font-size:12px;font-weight:600;color:#4e5969;margin-bottom:4px;display:block}}
.detail-text{{font-size:13px;color:#1d2129;line-height:1.7}}

.empty-state{{text-align:center;padding:60px 20px;color:#86909c;background:#fff;border-radius:8px}}

@media(max-width:700px){{.header{{flex-direction:column;align-items:flex-start}}.stats-bar{{flex-wrap:wrap}}.stat-item{{min-width:45%}}.filter-row{{flex-direction:column}}.search-box{{min-width:100%}}.filter-group{{width:100%}}.card-header{{flex-direction:column}}}}

.toast{{position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:8px 20px;border-radius:6px;font-size:13px;z-index:9999;color:#fff;background:#1d2129;animation:fadeIn .3s}}
@keyframes fadeIn{{from{{opacity:0;transform:translateX(-50%) translateY(-10px)}}to{{opacity:1;transform:translateX(-50%) translateY(0)}}}}
</style>
</head>
<body>
<div class="app">
<div class="header">
<div class="header-left"><h1>AI政策收集报告</h1><span class="sub">政府官网 · 智能筛选</span></div>
<div class="header-right">生成时间: {stats['generated_at']}</div>
</div>

<div class="stats-bar">
<div class="stat-item"><span class="stat-label">最近一周</span><span class="stat-value" id="stRecent">0</span></div>
<div class="stat-item"><span class="stat-label">已归档</span><span class="stat-value" id="stArchived">0</span></div>
<div class="stat-item"><span class="stat-label">AI政策总量</span><span class="stat-value" id="stAi">{stats['ai_related']}</span></div>
<div class="stat-item"><span class="stat-label">覆盖来源</span><span class="stat-value" id="stSrc">{len(stats['sources'])}</span></div>
</div>

<div class="filter-bar">
<div class="filter-row">
<div class="search-box"><input type="text" id="search" placeholder="搜索全文（标题、正文、关键词）..." oninput="doFilter()"></div>
<div class="filter-group">
<select id="sourceFilter" onchange="doFilter()"><option value="">全部来源</option></select>
<select id="typeFilter" onchange="doFilter()"><option value="">全部类型</option></select>
<select id="regionFilter" onchange="doFilter()"><option value="">全部区域</option></select>
<select id="sortFilter" onchange="doFilter()">
<option value="date">按时间 ↓</option>
<option value="score">按评分 ↓</option>
</select>
<label class="toggle-label"><input type="checkbox" id="archiveToggle" onchange="doFilter()"><span> 显示已归档</span></label>
<button id="refreshBtn" onclick="manualRefresh(this)" style="padding:6px 12px;border:1px solid #d9dde2;border-radius:6px;background:#fff;cursor:pointer;font-size:13px;color:#4e5969">&#x1f504; 刷新数据</button>
</div>
</div>
</div>

<div class="result-info" id="resultInfo">默认显示 <strong>最近一周</strong>的政策（<strong id="resultCount">0</strong> 条）| 已归档 <strong id="archivedCount">0</strong> 条（可勾选下方"显示已归档"查看）| 全量AI政策共 <strong id="totalCount">0</strong> 条</div>
<div class="policy-list" id="policyList"></div>
<div class="empty-state" id="emptyState" style="display:none">无匹配的政策信息</div>
</div>

<script>
var POLICIES = {data_json};
var SOURCES = {sources_json};
var TYPES = {types_json};
var REGIONS = {regions_json};
var currentData = POLICIES;
var _d = new Date(); _d.setDate(_d.getDate() - 7);
var RECENT_WEEK_START = _d.toISOString().slice(0, 10);

// 初始化
document.addEventListener('DOMContentLoaded', function(){{
    renderFilters();
    doFilter();
}});

function renderFilters() {{
    var sel = document.getElementById('sourceFilter');
    sel.innerHTML = '<option value="">全部来源</option>' + SOURCES.map(function(s){{return '<option value="'+s+'">'+s+'</option>'}}).join('');
    var tsel = document.getElementById('typeFilter');
    tsel.innerHTML = '<option value="">全部类型</option>' + TYPES.map(function(t){{return '<option value="'+t+'">'+t+'</option>'}}).join('');
    var rsel = document.getElementById('regionFilter');
    rsel.innerHTML = '<option value="">全部区域</option>' + REGIONS.map(function(r){{return '<option value="'+r+'">'+r+'</option>'}}).join('');
}}

function doFilter() {{
    var kw = document.getElementById('search').value.toLowerCase().trim();
    var src = document.getElementById('sourceFilter').value;
    var tp = document.getElementById('typeFilter').value;
    var rg = document.getElementById('regionFilter').value;
    var showArchived = document.getElementById('archiveToggle').checked;

    currentData = POLICIES.filter(function(p) {{
        // 默认只显示最近一周的政策（不勾选"显示已归档"时）
        if (!showArchived && (!p.publish_date || p.publish_date < RECENT_WEEK_START)) return false;
        if (src && p.source !== src) return false;
        if (tp && p.article_type !== tp) return false;
        if (rg && p.region !== rg) return false;
        if (kw) {{
            var inTitle = p.title.toLowerCase().indexOf(kw) !== -1;
            var inContent = (p.content_text || '').toLowerCase().indexOf(kw) !== -1;
            var inSummary = (p.summary || '').toLowerCase().indexOf(kw) !== -1;
            var inKws = (p.policy_keywords || '').toLowerCase().indexOf(kw) !== -1;
            if (!inTitle && !inContent && !inSummary && !inKws) return false;
        }}
        return true;
    }});

    var recentCount = POLICIES.filter(function(p) {{ return p.publish_date && p.publish_date >= RECENT_WEEK_START; }}).length;
    var archivedCount = POLICIES.filter(function(p) {{ return !p.publish_date || p.publish_date < RECENT_WEEK_START; }}).length;
    document.getElementById('stRecent').textContent = recentCount;
    document.getElementById('stArchived').textContent = archivedCount;
    document.getElementById('archivedCount').textContent = archivedCount;
    document.getElementById('totalCount').textContent = POLICIES.length;

    // 排序
    var sortBy = document.getElementById('sortFilter').value;
    currentData.sort(function(a, b) {{
        if (sortBy === 'date') {{
            var da = a.publish_date || '0000-00-00';
            var db = b.publish_date || '0000-00-00';
            return db.localeCompare(da);
        }} else {{
            return (b.ai_score || 0) - (a.ai_score || 0);
        }}
    }});

    document.getElementById('resultCount').textContent = currentData.length;
    renderList();
}}

function renderList() {{
    var list = document.getElementById('policyList');
    var empty = document.getElementById('emptyState');
    if (currentData.length === 0) {{
        list.innerHTML = '';
        empty.style.display = 'block';
        return;
    }}
    empty.style.display = 'none';
    list.innerHTML = currentData.map(buildCard).join('');
}}

function getAiSnippet(p) {{
    var AI_KWS = ["人工智能","大模型","大语言模型","AIGC","机器学习","深度学习","神经网络","自然语言处理","计算机视觉","语音识别","机器人","人形机器人","具身智能","自动驾驶","智能驾驶","智能网联汽车","无人驾驶","通用人工智能","AGI","智能体","AI芯片","智算","算力","智能平台","智能系统","人工智能平台","人工智能技术","无人机","智慧医疗","智能交通","脑机接口","大数据","数字化","智能制造","云计算","边缘计算","多模态","智能产业","AI","ChatGPT","GPT"];
    var text = (p.content_text || '');
    if (!text) return escapeH(p.summary || '(暂无正文)');
    var sentences = text.split(/[。！？\\n]+/).filter(function(s){{ return s.trim().length > 10; }});
    var best = null;
    var bestScore = 0;
    for (var i = 0; i < sentences.length; i++) {{
        var s = sentences[i];
        var score = 0;
        for (var j = 0; j < AI_KWS.length; j++) {{
            if (s.indexOf(AI_KWS[j]) !== -1) score++;
        }}
        if (score > bestScore) {{ bestScore = score; best = s; }}
    }}
    if (!best) return escapeH(p.summary || text.slice(0, 200) || '(暂无正文)');
    var raw = best.trim().slice(0, 250);
    var parts = [];
    var remaining = raw;
    while (remaining.length > 0) {{
        var found = -1;
        var foundKw = '';
        for (var k = 0; k < AI_KWS.length; k++) {{
            var idx = remaining.indexOf(AI_KWS[k]);
            if (idx !== -1 && (found === -1 || idx < found)) {{
                found = idx;
                foundKw = AI_KWS[k];
            }}
        }}
        if (found === -1) {{ parts.push(escapeH(remaining)); break; }}
        if (found > 0) parts.push(escapeH(remaining.slice(0, found)));
        parts.push('<mark>' + escapeH(foundKw) + '</mark>');
        remaining = remaining.slice(found + foundKw.length);
    }}
    return parts.join('');
}}

function buildCard(p) {{
    var badges = '';
    badges += '<span class="badge badge-ai">AI ' + Math.round(p.ai_score) + '分</span>';
    if (p.ai_score > 20) badges += '<span class="badge badge-high">高相关</span>';
    if (p.article_type) badges += '<span class="badge badge-type">' + p.article_type + '</span>';
    if (p.region) badges += '<span class="badge" style="background:#e8f5e9;color:#2e7d32">' + p.region + '</span>';
    if (p.is_archived === 1) badges += '<span class="badge badge-archived">归档</span>';

    var keywords = '';
    if (p.policy_keywords) {{
        p.policy_keywords.split('、').slice(0, 6).forEach(function(k) {{
            if (k) keywords += '<span class="kw-tag">' + k + '</span>';
        }});
    }}

    var dirTags = '';

    var summary = getAiSnippet(p);
    var pubDate = p.publish_date || (p.crawl_date || '').slice(0, 10) || '待识别';
    var src = p.source || '未知';

    return '<div class="policy-card" onclick="toggleDetail(this)">' +
        '<div class="card-header"><div class="card-title">' + escapeH(p.title) + '</div><div class="card-badges">' + badges + '</div></div>' +
        '<div class="card-meta"><span>' + pubDate + '</span><span>' + src + '</span></div>' +
        (keywords ? '<div class="card-keywords">' + keywords + '</div>' : '') +
        '<div class="card-summary">' + summary + '</div>' +
        '<div class="card-detail">' +
        (p.specific_measures ? '<div class="detail-section"><span class="detail-label">具体措施</span><div class="detail-text" style="white-space:pre-wrap">' + escapeH(p.specific_measures) + '</div></div>' : '') +
        (p.time_nodes ? '<div class="detail-section"><span class="detail-label">时间节点</span><div class="detail-text">' + p.time_nodes + '</div></div>' : '') +
        (p.responsible_entity ? '<div class="detail-section"><span class="detail-label">责任主体</span><div class="detail-text">' + p.responsible_entity + '</div></div>' : '') +
        '<div class="detail-section"><span class="detail-label">原文</span><div class="detail-text"><a href="' + p.url + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">' + escapeH(p.url.slice(0,80)) + '</a></div></div>' +
        (p.content_text ? '<div class="detail-section"><span class="detail-label">正文预览</span><div class="detail-text" style="white-space:pre-wrap;font-size:12px;color:#4e5969;max-height:400px;overflow:auto">' + escapeH(p.content_text.slice(0,6000)) + '</div></div>' : '') +
        '</div></div>';
}}

function toggleDetail(el) {{
    var d = el.querySelector('.card-detail');
    var open = d.classList.contains('open');
    document.querySelectorAll('.card-detail.open').forEach(function(e){{if(e!==d)e.classList.remove('open')}});
    d.classList.toggle('open');
}}

function escapeH(t) {{
    if (!t) return '';
    return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

function manualRefresh(btn) {{
    btn.disabled = true;
    btn.textContent = '⏳ 正在爬取...';
    // 尝试调用后端API刷新（需先启动服务: python3 app.py）
    fetch('http://localhost:5000/api/refresh', {{ method: 'POST' }})
        .then(function(r){{ return r.json() }})
        .then(function(data) {{
            if (data.success) {{
                btn.textContent = '✅ 爬取已启动（约2分钟完成），完成后请刷新页面';
                btn.disabled = false;
                setTimeout(function(){{ btn.textContent = '🔄 刷新数据'; }}, 5000);
            }} else {{
                btn.textContent = '⚠️ ' + data.message;
                btn.disabled = false;
                setTimeout(function(){{ btn.textContent = '🔄 刷新数据'; }}, 5000);
            }}
        }})
        .catch(function() {{
            btn.textContent = '⚠️ 未连接后端服务';
            btn.onclick = function() {{
                alert(
                    '请按以下步骤手动刷新：\\n\\n' +
                    '1. 在项目目录下运行: python3 app.py\\n' +
                    '   启动Web服务后访问 http://localhost:5000\\n' +
                    '   （首次爬取约2分钟完成）\\n\\n' +
                    '2. 或一键刷新运行: python3 refresh.py\\n' +
                    '   完成后重新打开 政策报告.html'
                );
                btn.textContent = '🔄 刷新数据';
            }};
            btn.disabled = false;
        }});
}}
</script>
</body>
</html>"""

    return html


def generate():
    """主入口：读取数据 → 生成HTML → 保存文件"""
    print(f"加载数据...")
    data = load_policies()
    crawl_log = load_crawl_log()
    print(f"  共 {len(data['policies'])} 条AI相关政策")

    print(f"生成HTML...")
    html = generate_html(data, crawl_log)

    output_path = OUTPUT_FILE
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"")
    print(f"  ✅ 报告已生成: {output_path}")
    print(f"  📊 {data['stats']['ai_related']} 条AI政策 | {len(data['stats']['sources'])} 个来源 | "
          f"生成于 {data['stats']['generated_at']}")
    print(f"  💡 双击文件即可在浏览器打开")
    return output_path


if __name__ == "__main__":
    generate()