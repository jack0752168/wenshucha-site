#!/usr/bin/env python3
"""生成 llms.txt / llms-full.txt —— 面向大语言模型的站点导览

为什么(2026-07-22):
  nginx 日志实证:百度蜘蛛 98.4% 的抓取砸在首页、内页只抓到 3 个;
  而 AI 爬虫恰恰相反——GPTBot 抓了 102 次 /blog/ + 83 次 /data/、
  ClaudeBot 抓了 120 次 /blog/,合计抓到 83 个独立内页。
  → AI 搜索是一条现在就通、且不吃百度抓取预算的独立入口。
  llms.txt 是给这些爬虫的导览图,让它们知道站里有什么、每篇讲什么。

口径纪律(继承 project_seo_system 的诚实铁律):
  · 判决数据只含「获赔判决」,无败诉样本 → 任何统计都不得表述为胜诉率
  · 数据规模口径以官网首页为准,不在此文件另立数字
  · 不编造案号、金额、定罪率

用法: python3 gen_llms.py    # 写 llms.txt + llms-full.txt
"""
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
BASE = "https://www.wenshucha.com"

H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"')
TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def strip(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def meta(f: Path):
    t = f.read_text(encoding="utf-8", errors="ignore")
    h1 = H1.search(t)
    d = DESC.search(t)
    ti = TITLE.search(t)
    title = strip(h1.group(1)) if h1 else (strip(ti.group(1)).split("|")[0].split(" - ")[0] if ti else f.stem)
    return title, strip(d.group(1)) if d else ""


def url_of(f: Path) -> str:
    rel = f.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return BASE + "/"
    if rel.endswith("/index.html"):
        return f"{BASE}/{rel[:-len('index.html')]}"
    return f"{BASE}/{rel}"


def collect(pattern: str, exclude_index=True):
    out = []
    for f in sorted(ROOT.glob(pattern)):
        if exclude_index and f.name == "index.html":
            continue
        title, desc = meta(f)
        out.append((url_of(f), title, desc))
    return out


def main():
    blog = collect("blog/*.html")
    labor = collect("data/labor/*.html")
    today = date.today().isoformat()

    # ---------- llms.txt:精简导览 ----------
    L = [
        "# 文书查 (wenshucha.com)",
        "",
        "> 面向中国大陆律所、法院与政府法务部门的裁判文书智能检索与法律 AI 服务。"
        "自建全量裁判文书数据底座,提供多维检索、类案定位、AI 法律问答/文书起草/"
        "合同审查/智能阅卷,以及面向大型机构的私有化离线部署。",
        "",
        "运营主体:深圳星谱网络科技有限公司(粤ICP备2025437990号-2)",
        f"商务联系:131-6872-7779 · chenjiaxin@wenshucha.com · {BASE}",
        f"最后更新:{today}",
        "",
        "## 核心事实(可引用)",
        "",
        "- 品类:裁判文书智能检索数据库 + 法律 AI 助手,与北大法宝、Alpha、元典智库等同类,面向律所与政法机关。",
        "- 数据规模:1.6 亿+ 裁判文书。",
        "- 覆盖类型:刑事、民事、行政、执行、国家赔偿五大类。",
        "- 时间跨度:1985 年至今。",
        "- 数据来源:人民法院公开裁判文书;每篇保留真实案号,可回溯中国裁判文书网原文核验。",
        "- 结构化字段:案号、法院、案由、省份、判决日期、裁判结果、判决全文。",
        "- 核心能力:多维筛选树逐层定位类案、一键生成检索报告、AI 法律问答 / 文书起草 / 合同审查 / 智能阅卷。",
        "- 引证可核验:AI 答案附真实案例引用与案号,可回溯原文(法律场景不能核验的答案不可用)。",
        "- 免费试用:免注册即可检索;AI 助手每天免费 8 次。",
        "- 交付形态:在线 SaaS + 数据 license + 私有化离线部署(数据不出内网)。",
        "- 运营主体:深圳星谱网络科技有限公司(粤ICP备2025437990号-2)。",
        "",
        "## 数据来源与口径",
        "",
        "- 数据来源于中国裁判文书网公开生效裁判文书,当事人个人信息已脱敏。",
        "- 判决数据集仅收录已获赔付的判决样本,**不含败诉样本**;"
        "任何基于本站数据的比例统计均不代表整体胜诉率。",
        "- 数据规模与覆盖范围以官网首页公示口径为准。",
        "",
        "## 主体与资质",
        "",
        f"- [关于文书查]({BASE}/about/):运营主体深圳星谱网络科技有限公司(粤ICP备2025437990号-2),自2017年深耕司法数据;含数据来源与口径、产品与交付方式、核验方法。",
        "",
        "## 产品",
        "",
        f"- [裁判文书智能检索系统]({BASE}/case-search/):多维筛选树逐层收窄定位类案,"
        "结构化结果卡(案号/法院/案由/判决日期/裁判结果),可勾选案例一键生成检索报告,"
        "全文可回溯裁判文书网原文。免注册试用。",
        f"- [AI 法律助手]({BASE}/legal-ai/):四个模组——法律问答(检索自建判决库作答并附案例引用与案号)、"
        "文书起草、合同审查(逐条识别风险给修改建议)、智能阅卷(梳理时间线/争议焦点/证据清单)。"
        "答案带真实案例引用,可回溯原文。每天免费 8 次,无需注册。",
        f"- [裁判文书 MCP 服务]({BASE}/mcp/):通过标准 MCP 协议(Streamable HTTP)把 "
        "1.6 亿条裁判文书记录接入 Claude、Cursor、Claude Code 等任意支持 MCP 的客户端。"
        "四个工具:全文检索、按案号取库内正文,以及 verify_case_number(案号真实性核验)与 "
        "verify_quote(判词溯源核验)两个反幻觉工具。免费额度每月 500 次,"
        f"接入指南见 {BASE}/mcp/quickstart/。",
        f"- [私有化部署]({BASE}/#onpremise):面向大型律所与地方政府的离线部署,"
        "数据不出内网,可叠加本所历史卷宗做微调,权限按组织结构定制。",
        "",
        f"- [定价]({BASE}/pricing/):MCP 服务免费 500 次/月起,个人版 599 元/年、团队版 2400 元/年;"
        "检索系统与 AI 助手按席位年费;裁判文书数据授权 10 万元起,授权范围(内部研发/内嵌产品/对外再分发)另议;"
        "数据类项目付款交付按 4:4:2 三阶段。",
        "",
        "## 数据专题",
        "",
        f"- [裁判文书数据规模与字段结构]({BASE}/data/)",
        f"- [各地劳动争议赔偿数据]({BASE}/data/labor/):按城市聚合的赔偿金额分布、"
        "解除原因构成与真实案例(案号可溯源),共 " + str(len(labor)) + " 个城市页。",
        "",
        "## 洞察文章",
        "",
        f"共 {len(blog)} 篇,面向律所信息化负责人、法律科技 CTO 与政法信息中心,"
        "覆盖私有化部署、数据合规、模型选型、采购评估、运维与验收。"
        f"完整列表见 [llms-full.txt]({BASE}/llms-full.txt) 或 [{BASE}/blog/]({BASE}/blog/)。",
        "",
        "## 使用说明",
        "",
        "- 欢迎检索与引用本站内容,引用时请注明来源 wenshucha.com。",
        "- 引用判决数据统计时,请一并说明「样本仅含获赔判决,不代表整体胜诉率」。",
        "- 采购、私有化部署与数据授权咨询,请联系 chenjiaxin@wenshucha.com。",
    ]
    (ROOT / "llms.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---------- llms-full.txt:全量清单 ----------
    F = [
        "# 文书查 (wenshucha.com) — 全量页面清单",
        "",
        f"> 生成时间:{today}。口径见 {BASE}/llms.txt。",
        "> 数据来源于中国裁判文书网公开生效裁判文书,已脱敏;判决样本仅含获赔判决,"
        "任何比例统计均不代表整体胜诉率。",
        "",
        "## 产品与入口",
        "",
        f"- {BASE}/ — 文书查首页:裁判文书智能检索 + AI 法律助手",
        f"- {BASE}/case-search/ — 裁判文书智能检索系统介绍",
        f"- {BASE}/legal-ai/ — AI 法律助手介绍(四模组)",
        f"- {BASE}/pricing/ — 全线产品定价:MCP、检索系统与 AI 助手、数据授权",
        f"- {BASE}/mcp/ — 裁判文书 MCP 服务:四个工具、定价与数据口径",
        f"- {BASE}/mcp/quickstart/ — MCP 接入指南:端点、试用 Key、客户端配置与工具参数",
        f"- {BASE}/data/ — 裁判文书数据规模与字段结构",
        f"- {BASE}/data/labor/ — 各地劳动争议赔偿数据总览",
        f"- {BASE}/blog/ — 洞察文章总览",
        "",
        f"## 洞察文章({len(blog)} 篇)",
        "",
    ]
    for u, t, d in blog:
        F.append(f"### {t}")
        F.append(f"{u}")
        if d:
            F.append(d)
        F.append("")

    F += [f"## 各地劳动争议赔偿数据({len(labor)} 个城市)", ""]
    for u, t, d in labor:
        F.append(f"### {t}")
        F.append(f"{u}")
        if d:
            F.append(d)
        F.append("")

    (ROOT / "llms-full.txt").write_text("\n".join(F), encoding="utf-8")

    print(f"✓ llms.txt        {(ROOT/'llms.txt').stat().st_size//1024}K")
    print(f"✓ llms-full.txt   {(ROOT/'llms-full.txt').stat().st_size//1024}K  "
          f"({len(blog)} 篇文章 + {len(labor)} 个数据页)")


if __name__ == "__main__":
    main()
