#!/usr/bin/env python3
"""部署前守门员 —— 内链完整性 + robots/sitemap 一致性检查

为什么有(2026-07-22):
  · 删首页板块后 146 处死锚点散在 83 个文件里躺了好几天,没人发现
  · robots.txt 的 Sitemap 指向非 www,301 上线后蜘蛛取 sitemap 吃跳转,13 个月没读过
  · /calc 404 被天天推给百度
  这类低级错不该靠人眼,deploy 前机器挡掉,有错就拒绝上线。

查四件事:
  1. 站内 <a href> 指向的文件必须存在(含 /dir/ → dir/index.html)
  2. 锚点 href="#x" / "/page#x" → 目标页里必须真有 id="x"
  3. robots.txt 的 Sitemap 必须是 https://www.wenshucha.com/(带 www,否则吃 301)
  4. sitemap.xml 里声明的每个 URL,本地必须有对应文件(承诺了就得兑现)

用法: python3 linkcheck.py [site_dir]   # 有错 exit 1(deploy 脚本据此中止)
"""
import re
import sys
from pathlib import Path

SITE = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent).resolve()
HOSTS = ("https://www.wenshucha.com", "https://wenshucha.com")

href_re = re.compile(r'href="([^"]+)"')
id_re = re.compile(r'id="([^"]+)"')


def local_target(path: str):
    """站内 path → 本地文件;不存在返回 None。"""
    p = path.split("?")[0]
    if p in ("", "/"):
        p = "/index.html"
    f = SITE / p.lstrip("/")
    if f.is_dir():
        f = f / "index.html"
    if f.suffix == "" and not f.exists():
        f2 = Path(str(f) + ".html")
        if f2.exists():
            return f2
    return f if f.exists() else None


def ids_of(f: Path, cache={}):
    if f not in cache:
        try:
            cache[f] = set(id_re.findall(f.read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            cache[f] = set()
    return cache[f]


def main() -> int:
    errors = []
    html_files = [f for f in SITE.rglob("*.html") if ".git" not in f.parts]

    for f in html_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        rel = f.relative_to(SITE)
        for href in href_re.findall(txt):
            h = href.strip()
            if h.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            # 站外链接不管(tob/peilema/sinoverdict 是别的部署)
            if h.startswith("http") and not h.startswith(HOSTS):
                continue
            for host in HOSTS:
                if h.startswith(host):
                    h = h[len(host):] or "/"
                    break
            path, _, frag = h.partition("#")
            if path.startswith("http"):
                continue
            # 相对路径:相对当前文件所在目录
            if path and not path.startswith("/"):
                tgt_path = "/" + str((f.parent / path).resolve().relative_to(SITE))
            else:
                tgt_path = path
            tgt = local_target(tgt_path) if tgt_path else f
            if tgt_path and tgt is None:
                errors.append(f"{rel}: 死链 href=\"{href}\" → 本地无 {tgt_path}")
                continue
            if frag and tgt is not None and frag not in ids_of(tgt):
                errors.append(f"{rel}: 死锚点 href=\"{href}\" → {tgt.relative_to(SITE)} 里没有 id=\"{frag}\"")

    # robots.txt: Sitemap 必须 www(非 www 会吃 301,蜘蛛就不读了 —— 2026-07-22 实证 13 个月 0 读取)
    robots = SITE / "robots.txt"
    if robots.exists():
        for line in robots.read_text().splitlines():
            if line.lower().startswith("sitemap:"):
                u = line.split(":", 1)[1].strip()
                if not u.startswith("https://www.wenshucha.com/"):
                    errors.append(f"robots.txt: Sitemap 必须带 www 直达(现在是 {u},会吃 301)")

    # sitemap.xml 承诺的页必须存在
    sm = SITE / "sitemap.xml"
    if sm.exists():
        for m in re.finditer(r"<loc>\s*([^<\s]+)\s*</loc>", sm.read_text(errors="ignore")):
            u = m.group(1)
            p = re.sub(r"^https?://[^/]+", "", u) or "/"
            if local_target(p.split("#")[0]) is None:
                errors.append(f"sitemap.xml: 声明了 {u} 但本地无此文件")

    if errors:
        print(f"✗ linkcheck 发现 {len(errors)} 个问题,拒绝部署:")
        for e in errors[:40]:
            print("  " + e)
        if len(errors) > 40:
            print(f"  …还有 {len(errors)-40} 条")
        return 1
    print(f"✓ linkcheck 通过:{len(html_files)} 个页面,内链/锚点/robots/sitemap 全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
