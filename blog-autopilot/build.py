"""gera o site estático do blog a partir de posts/*.md (pasta de saída: site/).

uso: python build.py
no cloudflare pages: comando de build "pip install markdown && python build.py", pasta de saída "site".
"""

import html
import json
import re
import shutil
from datetime import date
from email.utils import format_datetime
from datetime import datetime, timezone
from pathlib import Path

import markdown

BASE = Path(__file__).parent
POSTS = BASE / "posts"
SAIDA = BASE / "site"
CFG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
SITE = CFG["site_url"].rstrip("/")
NOME = CFG["site_nome"]
PRINCIPAL = CFG.get("site_principal", SITE)

CSS = """
:root{--bg:#fff;--fg:#14161a;--muted:#5d6470;--line:#e6e8ec;--accent:#2f5bff;--card:#f6f7f9}
@media (prefers-color-scheme:dark){:root{--bg:#0e1013;--fg:#eceef2;--muted:#9aa1ad;--line:#23272e;--accent:#7d9bff;--card:#161a20}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.7 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.wrap{max-width:720px;margin:0 auto;padding:0 16px}
header{border-bottom:1px solid var(--line)}
header .wrap{display:flex;justify-content:space-between;align-items:center;height:64px}
header a{color:var(--fg);text-decoration:none;font-weight:700}
header nav a{font-weight:500;color:var(--muted);margin-left:16px;font-size:15px}
main{padding:40px 0 64px}
h1{font-size:clamp(28px,5vw,40px);line-height:1.2;margin:0 0 12px}
h2{font-size:26px;line-height:1.3;margin:40px 0 12px}
h3{font-size:20px;margin:28px 0 8px}
.meta{color:var(--muted);font-size:15px;margin-bottom:32px}
article img{max-width:100%;height:auto}
table{width:100%;border-collapse:collapse;font-size:16px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:8px 12px;text-align:left}
th{background:var(--card)}
blockquote{margin:0;padding:4px 16px;border-left:3px solid var(--accent);color:var(--muted)}
.cta{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin-top:48px}
.cta a{display:inline-block;margin-top:8px;background:var(--accent);color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600}
ul.lista{list-style:none;padding:0}
ul.lista li{border-bottom:1px solid var(--line);padding:20px 0}
ul.lista a{font-size:21px;font-weight:650;text-decoration:none;color:var(--fg)}
ul.lista p{margin:6px 0 0;color:var(--muted)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:14px;padding:24px 0}
"""


def ler_post(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    meta = {}
    for linha in m.group(1).splitlines():
        chave, _, valor = linha.partition(":")
        meta[chave.strip()] = json.loads(valor.strip())
    corpo = re.sub(r"^# .*\n+", "", m.group(2), count=1)  # o h1 vem do título
    meta.setdefault("slug", re.sub(r"^\d{4}-\d{2}-\d{2}-", "", arquivo.stem))
    meta["html"] = markdown.markdown(corpo, extensions=["tables"])
    meta["url"] = f"{SITE}/{meta['slug']}/"
    return meta


def pagina(titulo, descricao, url, conteudo, extra_head=""):
    e = html.escape
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="{e(NOME)}">
<meta property="og:locale" content="pt_BR">
<link rel="alternate" type="application/rss+xml" title="{e(NOME)}" href="{SITE}/feed.xml">
<style>{CSS}</style>
{extra_head}
</head>
<body>
<header><div class="wrap"><a href="{SITE}/">{e(NOME)} · blog</a><nav><a href="{PRINCIPAL}">site</a><a href="{CFG['cta_url']}">contato</a></nav></div></header>
<main><div class="wrap">{conteudo}</div></main>
<footer><div class="wrap">© {date.today().year} {e(NOME)} · <a href="{PRINCIPAL}">{PRINCIPAL.removeprefix('https://')}</a></div></footer>
</body>
</html>
"""


def main():
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir()
    posts = sorted((ler_post(a) for a in POSTS.glob("*.md")), key=lambda p: p["date"], reverse=True)
    e = html.escape

    for p in posts:
        schema = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": p["title"],
            "description": p["description"],
            "datePublished": p["date"],
            "mainEntityOfPage": p["url"],
            "inLanguage": "pt-BR",
            "publisher": {"@type": "Organization", "name": NOME, "url": PRINCIPAL},
        }
        conteudo = f"""<article>
<h1>{e(p['title'])}</h1>
<div class="meta">{datetime.fromisoformat(p['date']).strftime('%d/%m/%Y')}</div>
{p['html']}
<div class="cta"><strong>{e(CFG['oferta'])}</strong><br><a href="{CFG['cta_url']}">falar com a {e(NOME)}</a></div>
</article>"""
        destino = SAIDA / p["slug"]
        destino.mkdir(parents=True)
        (destino / "index.html").write_text(
            pagina(f"{p['title']} | {NOME}", p["description"], p["url"], conteudo,
                   f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'),
            encoding="utf-8",
        )

    itens = "".join(
        f'<li><a href="{p["url"]}">{e(p["title"])}</a><p>{e(p.get("excerpt", p["description"]))}</p></li>' for p in posts
    ) or "<li><p>os primeiros artigos chegam em breve.</p></li>"
    (SAIDA / "index.html").write_text(
        pagina(f"Blog | {NOME}", f"artigos da {NOME}", f"{SITE}/", f"<h1>Blog</h1><ul class=\"lista\">{itens}</ul>"),
        encoding="utf-8",
    )

    urls = [f"{SITE}/"] + [p["url"] for p in posts]
    (SAIDA / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n",
        encoding="utf-8",
    )
    (SAIDA / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")

    rss = "".join(
        f"<item><title>{e(p['title'])}</title><link>{p['url']}</link><guid>{p['url']}</guid>"
        f"<pubDate>{format_datetime(datetime.fromisoformat(p['date']).replace(tzinfo=timezone.utc))}</pubDate>"
        f"<description>{e(p['description'])}</description></item>"
        for p in posts[:30]
    )
    (SAIDA / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{e(NOME)}</title>'
        f"<link>{SITE}/</link><description>blog da {e(NOME)}</description>{rss}</channel></rss>\n",
        encoding="utf-8",
    )
    print(f"{len(posts)} posts gerados em {SAIDA}")


if __name__ == "__main__":
    main()
