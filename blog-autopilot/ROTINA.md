# rotina: escrever 1 artigo do blog

instruções para a rotina agendada do claude code (sem custo de api: usa o plano do claude).

1. leia `blog-autopilot/config.json` e `blog-autopilot/keywords.csv`
2. pegue a primeira linha com status `pendente`. se não houver nenhuma, gere 20 palavras-chave novas de cauda longa para o nicho (sem repetir as existentes), adicione ao csv como `pendente` e use a primeira
3. escreva o artigo seguindo as regras de `system_prompt()` em `blog-autopilot/autopilot.py` (resposta direta no 1º parágrafo, h2/h3, lista ou tabela, sem inventar dados, 2 a 4 links internos para posts já publicados no csv, cta para `cta_url`, faq de 4 a 6 perguntas), com cerca de `palavras_por_artigo` palavras
4. salve em `blog-autopilot/posts/AAAA-MM-DD-<slug>.md` neste formato (valores do frontmatter em json):

   ```
   ---
   title: "título com a palavra-chave, até 65 caracteres"
   description: "meta description até 155 caracteres"
   excerpt: "resumo de 2 frases"
   slug: "slug-sem-acento"
   date: "AAAA-MM-DD"
   tags: ["tag1", "tag2"]
   ---
   # título

   corpo em markdown

   ## Perguntas frequentes

   ### pergunta

   resposta

   <script type="application/ld+json">{schema FAQPage com as mesmas perguntas}</script>
   ```

5. no csv, marque a linha como `publicado` e preencha `titulo`, `url` (`<site_url>/<slug>/`) e `publicado_em`
6. rode `pip install markdown && python blog-autopilot/build.py` e confirme que não deu erro
7. faça commit e push direto no `main` com a mensagem `blog: <título>`
