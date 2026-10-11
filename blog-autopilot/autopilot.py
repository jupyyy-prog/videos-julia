"""blog autopilot: gera artigos de SEO/GEO com Claude e publica no WordPress ou em markdown.

uso:
  python autopilot.py                 # escreve e publica os próximos artigos pendentes
  python autopilot.py --ideias 20     # sugere 20 palavras-chave novas e adiciona ao keywords.csv
  python autopilot.py --dry-run       # gera o artigo mas não publica nem marca como feito
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import anthropic
import markdown
import requests

BASE = Path(__file__).parent
CONFIG = BASE / "config.json"
KEYWORDS = BASE / "keywords.csv"
POSTS = BASE / "posts"
CAMPOS = ["keyword", "status", "titulo", "url", "publicado_em"]

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")

ARTIGO_SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string", "description": "título H1, até 65 caracteres, com a palavra-chave"},
        "slug": {"type": "string", "description": "slug curto, minúsculo, sem acento, com hífens"},
        "meta_description": {"type": "string", "description": "até 155 caracteres, com a palavra-chave e um gancho"},
        "resumo": {"type": "string", "description": "2 frases para o excerpt"},
        "conteudo_markdown": {"type": "string", "description": "corpo do artigo em markdown, sem o H1"},
        "faq": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"pergunta": {"type": "string"}, "resposta": {"type": "string"}},
                "required": ["pergunta", "resposta"],
                "additionalProperties": False,
            },
        },
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titulo", "slug", "meta_description", "resumo", "conteudo_markdown", "faq", "tags"],
    "additionalProperties": False,
}

IDEIAS_SCHEMA = {
    "type": "object",
    "properties": {"keywords": {"type": "array", "items": {"type": "string"}}},
    "required": ["keywords"],
    "additionalProperties": False,
}


def carregar_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def ler_keywords():
    with KEYWORDS.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def salvar_keywords(linhas):
    with KEYWORDS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for linha in linhas:
            w.writerow({c: linha.get(c, "") for c in CAMPOS})


def slugify(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:80]


def chamar_claude(client, system, prompt, schema):
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        resposta = stream.get_final_message()

    if resposta.stop_reason == "refusal":
        raise RuntimeError(f"o modelo recusou o pedido: {resposta.stop_details}")
    if resposta.stop_reason == "max_tokens":
        raise RuntimeError("resposta cortada por max_tokens; reduza palavras_por_artigo")
    texto = next(b.text for b in resposta.content if b.type == "text")
    u = resposta.usage
    print(f"  tokens: {u.input_tokens} entrada / {u.output_tokens} saída")
    return json.loads(texto)


def system_prompt(cfg):
    return f"""você é redator sênior de SEO e GEO (otimização para respostas de IAs como ChatGPT, Gemini e Perplexity).
escreve em {cfg['idioma']} para o blog de {cfg['site_nome']} ({cfg['site_url']}).

negócio: {cfg['nicho']}
público: {cfg['publico']}
oferta / CTA: {cfg['oferta']} — link: {cfg['cta_url']}
tom de voz: {cfg['tom_de_voz']}

regras do artigo:
- responda a intenção de busca logo no primeiro parágrafo, em 2 ou 3 frases diretas (é o trecho que IAs e o Google costumam citar)
- estrutura com H2 e H3 claros, parágrafos curtos, listas e, quando fizer sentido, uma tabela comparativa
- use a palavra-chave no primeiro parágrafo, em pelo menos um H2 e de forma natural no texto; inclua variações e termos relacionados
- traga dados concretos, exemplos práticos e passos acionáveis; nada de enchimento
- não invente estatísticas, estudos, preços ou citações; se não tiver certeza, fale de forma qualitativa
- quando receber artigos já publicados, insira de 2 a 4 links internos relevantes em markdown, usando as URLs exatas fornecidas
- termine com uma seção de conclusão e um CTA para a oferta, com o link {cfg['cta_url']}
- o FAQ (4 a 6 perguntas) vai no campo faq, não repita dentro do conteudo_markdown
- conteudo_markdown não inclui o H1 (o título vai separado)"""


def gerar_artigo(client, cfg, keyword, publicados):
    links = "\n".join(f"- {p['titulo']}: {p['url']}" for p in publicados if p.get("url")) or "(nenhum ainda)"
    prompt = f"""escreva um artigo de cerca de {cfg['palavras_por_artigo']} palavras para a palavra-chave principal:

"{keyword}"

artigos já publicados no blog (para links internos):
{links}"""
    return chamar_claude(client, system_prompt(cfg), prompt, ARTIGO_SCHEMA)


def faq_schema(faq):
    dados = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q["pergunta"], "acceptedAnswer": {"@type": "Answer", "text": q["resposta"]}}
            for q in faq
        ],
    }
    return f'<script type="application/ld+json">{json.dumps(dados, ensure_ascii=False)}</script>'


def montar_html(artigo):
    corpo = markdown.markdown(artigo["conteudo_markdown"], extensions=["tables"])
    faq = "".join(f"<h3>{q['pergunta']}</h3>\n<p>{q['resposta']}</p>\n" for q in artigo["faq"])
    return f"{corpo}\n<h2>Perguntas frequentes</h2>\n{faq}\n{faq_schema(artigo['faq'])}"


def publicar_wordpress(cfg, artigo):
    wp_url = os.environ["WP_URL"].rstrip("/")
    token = base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
    headers = {"Authorization": f"Basic {token}"}

    tag_ids = []
    for nome in artigo["tags"][:8]:
        r = requests.get(f"{wp_url}/wp-json/wp/v2/tags", params={"search": nome}, headers=headers, timeout=30)
        r.raise_for_status()
        existente = next((t for t in r.json() if t["name"].lower() == nome.lower()), None)
        if existente:
            tag_ids.append(existente["id"])
            continue
        r = requests.post(f"{wp_url}/wp-json/wp/v2/tags", json={"name": nome}, headers=headers, timeout=30)
        if r.ok:
            tag_ids.append(r.json()["id"])

    r = requests.post(
        f"{wp_url}/wp-json/wp/v2/posts",
        headers=headers,
        timeout=60,
        json={
            "title": artigo["titulo"],
            "slug": slugify(artigo["slug"]),
            "content": montar_html(artigo),
            "excerpt": artigo["resumo"],
            "status": cfg.get("status_wordpress", "draft"),
            "tags": tag_ids,
            # lido por Yoast/Rank Math quando o plugin expõe o campo na REST API
            "meta": {"_yoast_wpseo_metadesc": artigo["meta_description"], "rank_math_description": artigo["meta_description"]},
        },
    )
    if r.status_code == 400 and "meta" in r.text:
        # o site não expõe esses campos; publica sem meta description
        payload = json.loads(r.request.body)
        payload.pop("meta")
        r = requests.post(f"{wp_url}/wp-json/wp/v2/posts", headers=headers, timeout=60, json=payload)
    r.raise_for_status()
    return r.json()["link"]


def salvar_markdown(cfg, artigo):
    POSTS.mkdir(exist_ok=True)
    slug = slugify(artigo["slug"])
    faq = "\n".join(f"### {q['pergunta']}\n\n{q['resposta']}\n" for q in artigo["faq"])
    frontmatter = {
        "title": artigo["titulo"],
        "description": artigo["meta_description"],
        "excerpt": artigo["resumo"],
        "date": date.today().isoformat(),
        "tags": artigo["tags"],
    }
    linhas = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in frontmatter.items()] + ["---", ""]
    texto = "\n".join(linhas) + f"# {artigo['titulo']}\n\n{artigo['conteudo_markdown']}\n\n## Perguntas frequentes\n\n{faq}\n{faq_schema(artigo['faq'])}\n"
    caminho = POSTS / f"{date.today().isoformat()}-{slug}.md"
    caminho.write_text(texto, encoding="utf-8")
    return f"{cfg['site_url'].rstrip('/')}/blog/{slug}"


def rodar(client, cfg, dry_run):
    linhas = ler_keywords()
    pendentes = [l for l in linhas if l["status"].strip().lower() == "pendente"]
    if not pendentes:
        print("nenhuma palavra-chave pendente. rode: python autopilot.py --ideias 20")
        return
    publicados = [l for l in linhas if l["status"].strip().lower() == "publicado"]

    for linha in pendentes[: int(cfg.get("artigos_por_execucao", 1))]:
        print(f"escrevendo: {linha['keyword']}")
        artigo = gerar_artigo(client, cfg, linha["keyword"], publicados)
        if dry_run:
            print(json.dumps(artigo, ensure_ascii=False, indent=2)[:3000])
            continue
        url = publicar_wordpress(cfg, artigo) if cfg.get("destino") == "wordpress" else salvar_markdown(cfg, artigo)
        linha.update(status="publicado", titulo=artigo["titulo"], url=url, publicado_em=date.today().isoformat())
        publicados.append(linha)
        salvar_keywords(linhas)
        print(f"  ok: {url}")


def ideias(client, cfg, quantidade):
    linhas = ler_keywords()
    existentes = "\n".join(f"- {l['keyword']}" for l in linhas)
    prompt = f"""sugira {quantidade} palavras-chave de cauda longa para o blog, focadas em perguntas reais que o público faz no Google e em IAs.
priorize intenção informacional que leve naturalmente à oferta. nada de termos genéricos demais.
não repita nenhuma destas:
{existentes}"""
    novas = chamar_claude(client, system_prompt(cfg), prompt, IDEIAS_SCHEMA)["keywords"]
    ja = {l["keyword"].strip().lower() for l in linhas}
    for k in novas:
        if k.strip().lower() not in ja:
            linhas.append({"keyword": k.strip(), "status": "pendente"})
            print(f"+ {k}")
    salvar_keywords(linhas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ideias", type=int, help="gera N palavras-chave novas")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    cfg = carregar_config()
    client = anthropic.Anthropic()
    try:
        if args.ideias:
            ideias(client, cfg, args.ideias)
        else:
            rodar(client, cfg, args.dry_run)
    except anthropic.AuthenticationError:
        sys.exit("ANTHROPIC_API_KEY inválida ou ausente")
    except anthropic.RateLimitError:
        sys.exit("limite de uso da API atingido; tente mais tarde")
    except anthropic.APIStatusError as e:
        sys.exit(f"erro da API ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("sem conexão com a API da Anthropic")


if __name__ == "__main__":
    main()
