# Full report generator (DESIGN.md sec.6): 8 sections + per-brand pages.
# Self-contained HTML, no external dependencies, Chinese output.
# Visual rules follow the dataviz reference palette (validated default):
#   search layer = categorical slot 1 (blue), memory layer = slot 2 (orange),
#   fixed order, never cycled; text stays in ink tokens, never series colors;
#   verdict chips use status colors but always with a text label.
from __future__ import annotations

import re
from collections import Counter
from datetime import date

from . import analysis
from .models import Brand, ParsedAnswer

SEARCH_ENGINES = ("deepseek",)   # live-search grounded
MEMORY_ENGINES = ("zhipu",)      # answered from training memory (verified)

_TIER_CN = {"leader": "头部", "growth": "腰部", "emerging": "新锐"}
_VERDICT_CN = {"positive": "正面", "neutral": "中性", "negative": "负面", "hedged": "含糊"}
_COUNTRY_CN = {"CN": "中国出海", "INTL": "海外对照"}

REPORT_TITLE = "2026 出海清洁品牌 AI 可见性报告"


def _fmt_rate(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _fmt_pos(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}"


# ---------------------------------------------------------------- data layer

def split_engines(parsed: list[ParsedAnswer]) -> dict[str, list[ParsedAnswer]]:
    by: dict[str, list[ParsedAnswer]] = {}
    for p in parsed:
        by.setdefault(p.engine, []).append(p)
    return by


def freshness_rate(brand_name: str, pool: list[ParsedAnswer]) -> float | None:
    fq = [p for p in pool if p.dimension == "freshness" and p.brand == brand_name]
    if not fq:
        return None
    known = sum(1 for p in fq if p.freshness_known)
    return known / len(fq)


def brand_layer_metrics(brand: Brand, by_engine: dict) -> dict:
    """Two-layer metrics (search / memory) for one brand."""
    out = {}
    for role, engines in (("search", SEARCH_ENGINES), ("memory", MEMORY_ENGINES)):
        pool = [p for e in engines for p in by_engine.get(e, [])]
        descriptors = Counter(
            w.strip().lower()
            for p in pool
            for m in p.mentions if m.brand == brand.name
            for w in m.descriptors if w and w.strip()
        )
        out[role] = {
            "mention": analysis.mention_rate(brand.name, pool),
            "pos": analysis.avg_position(brand.name, pool),
            "verdict": analysis.verdict_distribution(brand.name, pool),
            "freshness": freshness_rate(brand.name, pool),
            "descriptors": [w for w, _ in descriptors.most_common(6)],
        }
    return out


# ------------------------------------------------------------- quote mining

def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def extract_quotes(brand: Brand, records: list[dict], max_quotes: int = 3) -> list[dict]:
    """Verbatim AI sentences about the brand, from its OWN trust questions.
    Mentions inside other brands' answers are ignored - a sentence naming
    Ecovacs inside a Roborock answer is not an Ecovacs verdict."""
    names = [brand.name] + list(brand.aliases or [])
    pat = re.compile(rf"\b(?:{'|'.join(re.escape(n) for n in names)})\b", re.IGNORECASE)
    own: list[dict] = []
    for r in records:
        if r.get("error") or not r.get("answer") or r.get("dimension") != "trust":
            continue
        if r.get("brand") != brand.name:
            continue
        for s in _sentences(r["answer"]):
            if pat.search(s) and 20 < len(s) < 300:
                own.append({"engine": r["engine"], "question": r.get("question", ""),
                            "text": s})
                break  # one quote per answer keeps variety across questions
    return own[:max_quotes]


# ------------------------------------------------ rule-based CN synthesis

def _lv(v: float | None) -> str | None:
    if v is None:
        return None
    if v == 0:
        return "zero"
    if v < 0.25:
        return "low"
    if v >= 0.5:
        return "high"
    return "mid"


def verdict_line(name: str, m: dict) -> str:
    s, mm = _lv(m["search"]["mention"]), _lv(m["memory"]["mention"])
    if s == "zero" and mm == "zero":
        line = f"{name} 在两层都接近隐形——AI 既不推荐它,训练语料里也没有稳定的品牌认知。"
    elif s in (None, "zero", "low") and mm in ("mid", "high"):
        line = f"{name} 是\"记忆里的老面孔\":AI 的训练语料还认它,但实时推荐已经把它跳过。"
    elif s in ("mid", "high") and mm in (None, "zero", "low"):
        line = f"{name} 是\"搜索层新贵\":实时推荐的常客,但还没被写进 AI 的记忆。"
    elif s in ("mid", "high") and mm in ("mid", "high"):
        line = f"{name} 双层在线:既有存量认知,又是实时推荐常客。"
    else:
        line = f"{name} 两层可见度都偏低,AI 推荐基本不带它玩。"
    verdict = m["search"]["verdict"]
    if verdict:
        if set(verdict) == {"hedged"}:
            line += "搜索层的信任裁决全部含糊其辞——AI 提它,但不敢为它背书。"
        elif set(verdict) == {"positive"}:
            line += "搜索层信任裁决全正面,是 AI 愿意背书的品牌。"
    return line


def action_steps(m: dict) -> list[str]:
    s, mm = m["search"]["mention"], m["memory"]["mention"]
    matched: list[str] = []
    if s is None or s < 0.25:
        matched.append(
            "搜索层进攻:让权威评测、垂直媒体、论坛讨论在 \"best …\" 类问题下出现你的品牌——"
            "联网 AI 的推荐直接来自这些实时语料。优先做 3-5 篇深度评测投放 + Reddit/权威站点的自然讨论。")
    if mm is None or mm < 0.25:
        matched.append(
            "记忆层沉淀:维基/百科词条、品牌官网的品牌故事与结构化数据、可被引用的权威报道——"
            "这些内容会进入下一代模型的训练语料,是\"过期不退\"的资产。")
    verdict = m["search"]["verdict"]
    if verdict and ("hedged" in verdict or "negative" in verdict):
        matched.append(
            "信任资产建设:公开的退换货/保修政策页、第三方口碑聚合、客服响应数据——"
            "AI 裁决\"靠不靠谱\"时引用的正是这类信号。")
    monitoring = "建立季度监测:两层六项指标(提及率/排位/裁决/新鲜度)按季度复测,量化每一步动作的回报。"
    return matched[:2] + [monitoring]


# ------------------------------------------------------------------- HTML

CSS = """
:root{color-scheme:light;
 --surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
 --grid:#e1e0d9;--baseline:#c3c2b7;--s1:#2a78d6;--s2:#eb6834;
 --good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--ring:rgba(11,11,11,.10)}
@media (prefers-color-scheme:dark){
:root:not([data-theme="light"]){color-scheme:dark;
 --surface:#1a1a19;--page:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;
 --grid:#2c2c2a;--baseline:#383835;--s1:#3987e5;--s2:#d95926;--ring:rgba(255,255,255,.10)}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
 font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.6}
main{max-width:960px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 4px} h2{font-size:20px;margin:44px 0 12px;
 border-bottom:1px solid var(--grid);padding-bottom:6px}
.sub{color:var(--ink2);font-size:14px}
nav{background:var(--surface);border:1px solid var(--ring);border-radius:8px;
 padding:10px 14px;margin:18px 0;font-size:13.5px}
nav a{color:var(--s1);text-decoration:none;margin-right:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:14px 16px}
.tile .num{font-size:30px;font-weight:700}
.tile .lab{color:var(--ink2);font-size:13px;margin-top:2px}
table{border-collapse:collapse;width:100%;background:var(--surface);
 border:1px solid var(--ring);font-size:13.5px}
th,td{border-bottom:1px solid var(--grid);padding:7px 10px;text-align:left}
th{color:var(--ink2);font-weight:600;background:rgba(134,134,128,.07)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.legend{display:flex;gap:16px;margin:10px 0 6px;font-size:13px;color:var(--ink2)}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.brow{display:grid;grid-template-columns:110px 1fr;align-items:center;gap:10px;margin:5px 0}
.blabel{font-size:13px;color:var(--ink2);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btrack{display:flex;flex-direction:column;gap:2px}
.bfill{height:10px;border-radius:0 4px 4px 0;min-width:2px}
.bfill.s1{background:var(--s1)} .bfill.s2{background:var(--s2)}
.bval{font-size:12px;color:var(--ink2);font-variant-numeric:tabular-nums;line-height:1}
.bwrap{display:flex;align-items:center;gap:6px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
.chip{font-size:12px;color:var(--ink2);border:1px solid var(--grid);border-radius:20px;padding:2px 10px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:0}
.page{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
 padding:18px 20px;margin:14px 0}
.page h3{margin:0 0 2px;font-size:17px}
.meta{color:var(--muted);font-size:12.5px;margin-bottom:8px}
.quote{border-left:3px solid var(--baseline);margin:8px 0;padding:4px 12px;color:var(--ink2);font-size:13.5px}
.quote .src{color:var(--muted);font-size:12px}
ol.steps{margin:8px 0 0;padding-left:20px;font-size:13.5px}
ol.steps li{margin:5px 0}
.note{color:var(--muted);font-size:12.5px}
footer{margin-top:50px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--grid);padding-top:12px}
@media print{.page{page-break-inside:avoid}nav{display:none}}
"""

_VERDICT_COLOR = {"positive": "var(--good)", "negative": "var(--crit)",
                  "hedged": "var(--warn)", "neutral": "var(--baseline)"}


def _chips(verdict: dict) -> str:
    if not verdict:
        return '<span class="note">无裁决数据</span>'
    parts = []
    for k, n in verdict.items():
        cn = _VERDICT_CN.get(k, k)
        parts.append(f'<span class="chip"><span class="dot" style="background:{_VERDICT_COLOR.get(k)}"></span>{cn} ×{n}</span>')
    return "".join(parts)


def _pair_bars(name: str, search: float | None, memory: float | None) -> str:
    def width(v):
        return 0.0 if not v else v * 85.0  # leave room for the value label

    return (
        f'<div class="brow"><div class="blabel" title="{name}">{name}</div>'
        f'<div class="btrack">'
        f'<div class="bwrap"><div class="bfill s1" style="width:{width(search):.1f}%"'
        f' title="{name} 搜索层提及率 {_fmt_rate(search)}"></div>'
        f'<span class="bval">{_fmt_rate(search)}</span></div>'
        f'<div class="bwrap"><div class="bfill s2" style="width:{width(memory):.1f}%"'
        f' title="{name} 记忆层提及率 {_fmt_rate(memory)}"></div>'
        f'<span class="bval">{_fmt_rate(memory)}</span></div>'
        f'</div></div>'
    )


def _brand_page(brand: Brand, m: dict, quotes: list[dict]) -> str:
    steps = "".join(f"<li>{s}</li>" for s in action_steps(m))
    descs = "、".join(m["search"]["descriptors"][:6]) or "—"
    quote_html = "".join(
        f'<div class="quote">“{q["text"]}”<div class="src">—— {q["engine"]} 对 “{q["question"]}” 的回答</div></div>'
        for q in quotes) or '<div class="note">本次样本未捕获到直接评论。</div>'
    return f"""
<div class="page" id="brand-{brand.name.lower().replace(' ', '-')}">
  <h3>{brand.name}</h3>
  <div class="meta">{_TIER_CN.get(brand.tier, brand.tier)} · {_COUNTRY_CN.get(brand.country, brand.country)}
   · {brand.domain or "域名待核"} · 样本内竞品:{("/".join(brand.competitors[:3])) or "—"}</div>
  <p style="margin:8px 0"><strong>一句话裁决:</strong>{verdict_line(brand.name, m)}</p>
  {_pair_bars(brand.name, m['search']['mention'], m['memory']['mention'])}
  <div class="legend"><span><span class="sw" style="background:var(--s1)"></span>搜索层提及率</span>
  <span><span class="sw" style="background:var(--s2)"></span>记忆层提及率</span></div>
  <table>
    <tr><th>指标</th><th class="num">搜索层</th><th class="num">记忆层</th></tr>
    <tr><td>提及率</td><td class="num">{_fmt_rate(m['search']['mention'])}</td><td class="num">{_fmt_rate(m['memory']['mention'])}</td></tr>
    <tr><td>出现时平均排位</td><td class="num">{_fmt_pos(m['search']['pos'])}</td><td class="num">{_fmt_pos(m['memory']['pos'])}</td></tr>
    <tr><td>新鲜度认知率</td><td class="num">{_fmt_rate(m['search']['freshness'])}</td><td class="num">{_fmt_rate(m['memory']['freshness'])}</td></tr>
  </table>
  <p style="margin:10px 0 2px"><strong>信任裁决(搜索层):</strong></p><div class="chips">{_chips(m['search']['verdict'])}</div>
  <p style="margin:10px 0 2px"><strong>AI 常用描述词:</strong>{descs}</p>
  <p style="margin:10px 0 2px"><strong>AI 原话:</strong></p>{quote_html}
  <p style="margin:10px 0 2px"><strong>三步走建议:</strong></p><ol class="steps">{steps}</ol>
</div>"""


def generate_report(brands: list[Brand], parsed: list[ParsedAnswer],
                    records: list[dict]) -> str:
    by_engine = split_engines(parsed)
    metrics = {b.name: brand_layer_metrics(b, by_engine) for b in brands}

    ranked = sorted(brands, key=lambda b: -(metrics[b.name]["search"]["mention"] or 0))
    search_zero = [b for b in brands if metrics[b.name]["search"]["mention"] == 0]
    both_zero = [b for b in brands
                 if metrics[b.name]["search"]["mention"] == 0
                 and metrics[b.name]["memory"]["mention"] == 0]

    n_disc = len({p.qid for p in parsed if p.dimension == "discovery"})
    n_qa = len(records)

    # section 3: ranking chart
    bars = "".join(
        _pair_bars(b.name, metrics[b.name]["search"]["mention"],
                   metrics[b.name]["memory"]["mention"])
        for b in ranked[:16])

    # section 5: tier/country per layer
    def _layer_tables() -> str:
        rows = []

        def rates(pool_filter):
            out = {}
            for role, engines in (("search", SEARCH_ENGINES), ("memory", MEMORY_ENGINES)):
                pool = [p for e in engines for p in by_engine.get(e, [])]
                out[role] = pool
            return out

        pools = rates(None)
        tiers = sorted({b.tier for b in brands})
        trs = ""
        for t in tiers:
            tb = [b for b in brands if b.tier == t]
            s = analysis.tier_comparison(tb, pools["search"]).get(t)
            mm = analysis.tier_comparison(tb, pools["memory"]).get(t)
            trs += (f"<tr><td>{_TIER_CN.get(t, t)}({len(tb)}个)</td>"
                    f"<td class='num'>{_fmt_rate(s)}</td><td class='num'>{_fmt_rate(mm)}</td></tr>")
        for c in ("CN", "INTL"):
            cb = [b for b in brands if b.country == c]
            s = analysis.country_comparison(cb, pools["search"]).get(c)
            mm = analysis.country_comparison(cb, pools["memory"]).get(c)
            trs += (f"<tr><td>{_COUNTRY_CN.get(c, c)}({len(cb)}个)</td>"
                    f"<td class='num'>{_fmt_rate(s)}</td><td class='num'>{_fmt_rate(mm)}</td></tr>")
        return f"<table><tr><th>分组</th><th class='num'>搜索层平均提及率</th><th class='num'>记忆层平均提及率</th></tr>{trs}</table>"

    # section 4: full league table
    league_rows = ""
    for i, b in enumerate(ranked, 1):
        m = metrics[b.name]
        league_rows += (
            f"<tr><td>{i}</td><td>{b.name}</td><td>{_TIER_CN.get(b.tier, b.tier)}</td>"
            f"<td>{_COUNTRY_CN.get(b.country, b.country)}</td>"
            f"<td class='num'>{_fmt_rate(m['search']['mention'])}</td>"
            f"<td class='num'>{_fmt_pos(m['search']['pos'])}</td>"
            f"<td class='num'>{_fmt_rate(m['memory']['mention'])}</td>"
            f"<td class='num'>{_fmt_rate(m['search']['freshness'])}</td></tr>")

    brand_pages = "".join(
        _brand_page(b, metrics[b.name], extract_quotes(b, records)) for b in ranked)

    def safe(name: str, role: str, key: str) -> float | None:
        return metrics.get(name, {}).get(role, {}).get(key)

    tile_rock_m = safe('Roborock', 'search', 'mention')
    tile_rock_p = safe('Roborock', 'search', 'pos')
    tile_eco_s = safe('Ecovacs', 'search', 'mention')
    tile_eco_m = safe('Ecovacs', 'memory', 'mention')
    tile_neato_m = safe('Neato', 'memory', 'mention')

    nav = "".join(
        f'<a href="#brand-{b.name.lower().replace(" ", "-")}">{b.name}</a>' for b in ranked)

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{REPORT_TITLE}</title><style>{CSS}</style></head>
<body><main>
<h1>{REPORT_TITLE}</h1>
<div class="sub">品类:智能清洁设备(扫地机/洗地机/吸尘器) · {len(brands)} 个品牌 · {n_qa} 次 AI 问答 · {date.today().isoformat()}</div>
<nav><a href="#s1">核心发现</a><a href="#s2">方法论</a><a href="#s3">推荐格局</a><a href="#s4">总榜</a>
<a href="#s5">分层对比</a><a href="#s6">单品牌页</a><a href="#s7">优化路径</a></nav>

<h2 id="s1">一、核心发现</h2>
<div class="tiles">
 <div class="tile"><div class="num">{len(search_zero)}/{len(brands)}</div><div class="lab">品牌在搜索层提及率为 0</div></div>
 <div class="tile"><div class="num">{len(both_zero)}/{len(brands)}</div><div class="lab">品牌两层完全隐身</div></div>
 <div class="tile"><div class="num">{_fmt_rate(tile_rock_m)}</div><div class="lab">石头搜索层提及率(平均排位 {_fmt_pos(tile_rock_p)},全场第一)</div></div>
 <div class="tile"><div class="num">{_fmt_rate(tile_eco_s)}</div><div class="lab">科沃斯搜索层提及率(IDC 全球出货第二)vs 记忆层 {_fmt_rate(tile_eco_m)}</div></div>
 <div class="tile"><div class="num">{_fmt_rate(tile_neato_m)}</div><div class="lab">已停产品牌 Neato 的记忆层提及率(AI 记忆里还活着)</div></div>
</div>
<ul style="font-size:14px">
 <li><strong>推荐高度集中:</strong>AI 的默认推荐列表只有 5-8 个位置,头部两家拿走大部分注意力,集中度高于任何货架渠道。</li>
 <li><strong>提及 ≠ 信任:</strong>iRobot 提及率居前,但搜索层信任裁决全部含糊;石头是唯一双引擎全正面的品牌。</li>
 <li><strong>社交电商爆发买不来 AI 可见性:</strong>TikTok 爆款新锐提及率全为 0,信任裁决全部含糊。</li>
</ul>

<h2 id="s2">二、方法论</h2>
<p style="font-size:14px">
样本:{len(brands)} 个智能清洁品牌(中国出海 {sum(1 for b in brands if b.country=='CN')} 个,海外对照 {sum(1 for b in brands if b.country=='INTL')} 个,按头部/腰部/新锐分层)。
问题集:{n_disc} 个品类发现型问题("best robot vacuum for pet hair"类)+ 每品牌 10 个问题(对比/信任/价格/新鲜度),共 {n_qa} 次真实问答。
测量引擎两层:<strong>搜索层</strong>(联网搜索作答)与<strong>记忆层</strong>(训练记忆作答,经探针验证该引擎未执行联网工具)。
指标:提及率、出现排位、信任裁决、新鲜度认知率、描述词。
</p>
<p class="note">局限:品类发现型问题 n={n_disc};排位按回答中首次出现顺序近似;本次为国内引擎,海外买家引擎(ChatGPT/Perplexity/Gemini)对照在下一版补齐,方法一致、可复现;两引擎均不返回引用来源,"引用来源分布"维度留待接入带引用的引擎后补充。品牌名匹配含产品线别名(如 Roomba→iRobot、Deebot→Ecovacs)。</p>

<h2 id="s3">三、品类 AI 推荐格局(提及率前 16)</h2>
<div class="legend"><span><span class="sw" style="background:var(--s1)"></span>搜索层提及率</span>
<span><span class="sw" style="background:var(--s2)"></span>记忆层提及率</span></div>
{bars}
<p class="note">完整 32 品牌数据见第四节总榜与第六节单品牌页。</p>

<h2 id="s4">四、品牌可见性总榜</h2>
<table><tr><th>#</th><th>品牌</th><th>层</th><th>国别</th>
<th class="num">搜索层提及率</th><th class="num">搜索层排位</th>
<th class="num">记忆层提及率</th><th class="num">新鲜度认知</th></tr>
{league_rows}</table>

<h2 id="s5">五、分层与中外对比</h2>
{_layer_tables()}
<p class="note">两层分开呈现,不引用混合均值——记忆层反映训练语料存量,搜索层反映实时推荐格局,混在一起会互相稀释。</p>

<h2 id="s6">六、单品牌页:AI 眼中的你</h2>
<nav>{nav}</nav>
{brand_pages}

<h2 id="s7">七、优化路径(从数据反推)</h2>
<ol style="font-size:14px">
 <li><strong>搜索层入口(实时语料):</strong>权威评测媒体投放、Reddit/垂直论坛自然讨论、新闻稿中的事实性数据——联网 AI 推荐直接读取这些源。</li>
 <li><strong>记忆层沉淀(训练语料):</strong>维基/百科词条、官网品牌故事与结构化数据、可引用的权威报道,进入下一代模型的训练集。</li>
 <li><strong>信任资产:</strong>公开透明的保修/退换政策页、第三方口碑聚合、评测中的可验证数据点——AI 裁决"靠不靠谱"的依据。</li>
 <li><strong>新鲜度维护:</strong>新品发布确保有时效性内容(新闻稿/评测)可被检索,AI 对"2026 年新品"的回答依赖它们。</li>
 <li><strong>季度监测:</strong>六项指标按季度复测,像盯 SEO 排名一样盯 AI 可见性。</li>
</ol>

<footer>{REPORT_TITLE} · 首版(国内引擎版)· 数据采集 {date.today().isoformat()} ·
方法与局限见第二节 · 本报告基于公开问答数据,品牌相关结论均为数据陈述</footer>
</main></body></html>"""


def generate_brand_onepager(brand: Brand, parsed: list[ParsedAnswer],
                            records: list[dict]) -> str:
    """Standalone per-brand page: one brand, one shareable file."""
    by_engine = split_engines(parsed)
    m = brand_layer_metrics(brand, by_engine)
    quotes = extract_quotes(brand, records)
    page = _brand_page(brand, m, quotes)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{brand.name} · AI 可见性体检页</title><style>{CSS}</style></head>
<body><main>
<h1>{brand.name}:AI 眼中的你</h1>
<div class="sub">出自《{REPORT_TITLE}》单品牌页 · {date.today().isoformat()} ·
完整报告含 32 个品牌横向对比</div>
{page}
<footer>数据来自公开 AI 问答实测({len(records)} 条样本的一部分),
指标定义与局限见完整报告方法论章节。</footer>
</main></body></html>"""
