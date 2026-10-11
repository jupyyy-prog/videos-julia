# blog autopilot

ferramenta própria pra escrever e publicar artigos de blog no automático, otimizados pro google e pra aparecer em respostas de ia (chatgpt, gemini, perplexity). mesma ideia do clickhunt, sem mensalidade: você paga só o uso da api do claude (centavos por artigo).

## blog da weltrix: blog.weltrixads.com.br (cloudflare pages, grátis)

o blog é um site estático gerado por `build.py` a partir da pasta `posts/`. o cloudflare pages refaz o site sozinho a cada commit.

configurar uma vez no cloudflare (https://dash.cloudflare.com):

1. workers & pages → create → pages → connect to git → escolhe o repositório `videos-julia`
2. production branch: `main`
3. build command: `pip install markdown && python build.py`
4. build output directory: `site`
5. root directory: `blog-autopilot`
6. depois do primeiro deploy: custom domains → `blog.weltrixads.com.br` (como o domínio já está no cloudflare, o dns é criado sozinho)
7. no google search console (https://search.google.com/search-console), adiciona o `blog.weltrixads.com.br` e envia o `sitemap.xml`

dois jeitos de escrever os artigos:

- **sem custo**: rotina agendada do claude code seguindo `ROTINA.md` (usa o teu plano do claude)
- **api do claude**: `autopilot.py` + github actions (centavos por artigo, detalhes abaixo)

## o que ela faz

- pega a próxima palavra-chave pendente em `keywords.csv`
- escreve o artigo com o claude: resposta direta no início, h2/h3, tabela, faq e cta pra tua oferta
- coloca links internos pros artigos que já foram publicados
- adiciona o schema de faq (json-ld), que ajuda o google e as ias a citarem o artigo
- publica no wordpress (como rascunho ou já publicado) ou salva em markdown na pasta `posts/`
- marca a palavra-chave como publicada e guarda a url
- roda sozinha seg, qua e sex pelo github actions
- `--ideias 20` gera 20 palavras-chave novas pro teu nicho

## custo

- github actions: grátis (o plano gratuito inclui 2.000 minutos por mês, e cada execução leva uns 2 minutos)
- api do claude: estimativa de ~us$0,10–0,30 por artigo de 1.500 palavras. 12 artigos por mês ≈ us$2–4
- o preço é pelo uso, não tem mensalidade

## configurar (uma vez só)

1. **chave da api do claude**
   - cria a conta em https://console.anthropic.com, coloca uns us$5 de crédito e gera uma api key
2. **edita o `config.json`**
   - `nicho`, `publico`, `oferta`, `cta_url`, `tom_de_voz`: quanto mais específico, melhor o texto
   - `destino`: `"wordpress"` pra publicar direto no site, ou `"markdown"` pra salvar os arquivos em `posts/`
   - `status_wordpress`: `"draft"` (você revisa antes; recomendado no começo) ou `"publish"`
   - `artigos_por_execucao`: quantos artigos escreve por vez
3. **se for wordpress**
   - no painel do wp: usuários → perfil → "senhas de aplicativo" → gera uma senha
4. **cadastra os segredos no github**
   - no repositório: settings → secrets and variables → actions → new repository secret
   - `ANTHROPIC_API_KEY`: a chave do passo 1
   - `WP_URL`: ex. `https://meusite.com.br` (só pra wordpress)
   - `WP_USER`: teu usuário do wp (só pra wordpress)
   - `WP_APP_PASSWORD`: a senha de aplicativo do passo 3 (só pra wordpress)
5. **palavras-chave**
   - apaga a linha de exemplo do `keywords.csv` e coloca as tuas com status `pendente`
   - ou vai em actions → blog autopilot → run workflow e preenche "ideias" com `20`

pronto. a partir daí roda sozinho seg, qua e sex às 9h17. pra rodar na hora: actions → blog autopilot → run workflow.

## rodar no próprio computador (opcional)

```bash
cd blog-autopilot
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python autopilot.py --ideias 20   # gera palavras-chave
python autopilot.py --dry-run     # mostra um artigo sem publicar
python autopilot.py               # escreve e publica
```

## ajustes

- modelo: por padrão usa o claude opus 5.5 com esforço `medium`. pra baratear, define `CLAUDE_MODEL=claude-sonnet-5-5` ou `CLAUDE_EFFORT=low`
- frequência: muda o `cron` em `.github/workflows/blog-autopilot.yml`
- recusa do modelo: a ferramenta usa o fallback automático da anthropic (`fallbacks: "default"`); se mesmo assim o modelo recusar, a execução para com erro e nada é publicado
