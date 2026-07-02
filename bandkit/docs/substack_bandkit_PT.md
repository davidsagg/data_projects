# #N — BandKit: Construindo um Companion de Palco para Bandas

### Transformando uma pilha de cifras em PDF numa setlist ao vivo e transponível — e o que aprendi construindo do início ao fim

> **Nota de formato para o Substack:** cole direto no editor. Onde houver um marcador `📷 [Imagem: ...]`, insira o screenshot ou diagrama correspondente. Ajuste o número do post (`#N`) para o próximo da sua série *Case Studies*. O subtítulo sugerido é a linha em itálico acima; tags sugeridas: `build-to-learn`, `react`, `fastapi`, `music-tech`.

📷 [Imagem: modo músico do BandKit — uma cifra na tela escura de palco, com os controles de transposição visíveis]

#### **Introdução e Contexto**

Quem já tocou ao vivo conhece o pequeno caos por trás de um show. A setlist mora numa mensagem de WhatsApp, as cifras moram numa pasta de PDFs (ou num caderno físico), o "quem toca o quê" mora na cabeça de alguém, e no instante em que o vocalista pede uma música *"um tom abaixo"*, todo mundo se atrapalha. As ferramentas que existem são ótimas em **cifras** (iReal Pro, Piascore) ou ótimas em **organização** (Notion, planilhas) — raramente as duas, e quase nunca otimizadas para o contexto que mais importa: **estar no palco, sob as luzes, sem tempo para mexer em ajustes.**

O BandKit é a minha tentativa de fechar essa lacuna: um único web app **local-first** que cuida de todo o ciclo de um show — calendário, biblioteca de músicas, setlist, e uma visão de palco onde cada músico transpõe e navega pelas cifras em tempo real, do próprio celular.

Mas há um segundo motivo, mais honesto, para este projeto existir. O BandKit faz parte do meu portfólio **"Build To Learn"** — projetos que construo de ponta a ponta especificamente para crescer como engenheiro. Vindo de dois projetos pesados em Python/dados (MusicDNA AI e Trend Radar), escolhi de propósito um projeto que me forçasse a entrar em território desconhecido: um frontend React de verdade, um problema de UX de modo duplo, um algoritmo de domínio escrito do zero e restrições de funcionamento offline. Este artigo é a história dessa construção.

> **Build To Learn:** a prática de escolher um projeto não pela feature que ele entrega, mas pelas habilidades específicas que ele obriga você a desenvolver. O produto é real; a saída principal é o aprendizado.

A pergunta que me propus a responder era simples de enunciar e difícil de executar:

- **Um único app local consegue servir dois usuários completamente diferentes — um "organizador" tranquilo e um "performer" sob pressão — a partir dos mesmos dados, e fazer o trabalho pesado de teoria musical (transposição) de forma instantânea e correta?**

#### **Entendendo o Problema**

Antes de escrever código, estruturei o projeto num charter formal: dois modos, uma plataforma.

O **modo Admin** é a superfície de planejamento — um calendário de shows, ensaios e gravações; uma biblioteca de músicas alimentada por uploads de PDF; e um montador de setlist com arrastar e soltar por evento, incluindo quem toca cada música.

O **modo Músico** é a superfície de palco — deliberadamente enxuto. A setlist do próximo show numa barra lateral; toque numa música e a cifra completa preenche a tela em fonte grande sobre fundo escuro; `+` / `−` transpõem todos os acordes na hora; `←` / `→` pulam entre seções. A tela nunca apaga, e tudo funciona offline.

📷 [Imagem: modo Admin — calendário e montador de setlist lado a lado]

A metodologia espelhou como conduzo projetos reais: **7 fases** — charter, user stories, casos de teste, desenvolvimento XP, TDD, otimização e deploy — cada uma documentada ao longo do caminho. Essa estrutura não é burocracia; é o que permitiu que uma construção solo se mantivesse honesta quanto a escopo e qualidade.

#### **O Coração Técnico — O Pipeline de Cifras**

A funcionalidade que faz ou quebra o BandKit é o pipeline que transforma um **PDF digital de cifra** numa **partitura estruturada e transponível**. Ele roda em quatro estágios:

📷 [Imagem: `docs/images/bandkit_chord_pipeline.png` — pronta para upload]

1. **Extração.** O `pdfplumber` puxa o texto bruto do PDF preservando o layout das linhas — o que importa, porque o sentido de uma cifra vive no *alinhamento vertical* dos acordes sobre a letra.
2. **Parsing.** Um parser próprio marca cada linha como *linha de acorde*, *linha de letra* ou *seção* (`[Intro]`, `[Verso]`, `[Refrão]`) usando regex e heurística, e emite um formato proprietário **BandKit ChordPro** (`.bkcp`).
3. **Transposição.** Uma engine feita do zero desloca cada acorde em N semitons.
4. **Renderização.** O React desenha os acordes alinhados sobre as sílabas corretas, no visualizador otimizado para palco.

A engine de transposição é a peça de que mais me orgulho, porque é modelagem de domínio pura. Ela segue a teoria cromática padrão de 12 semitons:

> **Transposição:** mover cada nota (e, portanto, cada acorde) de uma peça para cima ou para baixo pelo mesmo intervalo, de modo que a música soe em um novo tom mantendo intactas suas relações internas.

Cada acorde é dividido em **raiz** e **sufixo** — `C#m7` vira raiz `C#` e sufixo `m7`. A raiz é normalizada para equivalentes enarmônicos (`Db → C#`), deslocada N posições na escala cromática, e o acorde é reconstruído. Assim, `transpose("Am", +3)` retorna `C#m`, e a letra nunca é tocada.

Uma decisão sutil, porém importante: **espelhei essa lógica exata em JavaScript** no frontend. A ação mais sensível a latência de todo o app é o músico apertar `−1` no meio da música. Fazer isso com uma ida e volta à rede seria um atraso perceptível no palco. Espelhar o algoritmo tornou a operação instantânea.

#### **O Que Explorei (e Onde Ficou Difícil)**

**A UX de modo duplo acabou sendo um problema de dados, não de UI.** Meu primeiro modelo amarrava a ordem de execução no palco diretamente à setlist de planejamento. Isso desmoronou no momento em que uma banda quis *planejar* um show numa ordem e *tocar* em outra. A solução foi modelar uma entidade `MusicalExecution` independente da setlist — um refactor, não uma pintura nova. Lição: quando uma UI parece estranha, olhe primeiro para o schema por baixo dela.

**Cifras do mundo real são gloriosamente bagunçadas.** PDFs por aí misturam tablatura, diagramas de acordes e até marcadores de tom em espanhol (`Tono:`). Nenhum parser vai ser perfeito contra isso, então, em vez de perseguir 100% de extração, construí duas coisas: heurísticas que acertam a maioria das cifras, e um fallback de edição manual sempre disponível (editar o `.bkcp` direto) para o resto. Projetar para o caso de falha desde o início foi mais valioso do que polir o caminho feliz.

**Offline é uma restrição de engenharia, não um checkbox.** Palcos e bares têm Wi-Fi terrível. O BandKit é um PWA com Service Worker (Workbox, StaleWhileRevalidate) para continuar funcionando após o primeiro carregamento, e usa a **WakeLock API** para impedir que os celulares apaguem no meio da música — um detalhe minúsculo que fica completamente óbvio na primeira vez que ele te salva.

**TDD em duas linguagens.** O backend cresceu sob `pytest` (37 testes, 85% de cobertura); as peças React críticas — o visualizador de cifras e os controles de transposição — sob `Vitest` e Testing Library (6 testes). Terminar em **43 testes verdes** não era sobre um número; era sobre poder refatorar o modelo de setlist (veja acima) sem medo.

📷 [Imagem: terminal — saída de `make test` mostrando 43 testes passando]

As arestas ásperas raramente estavam no algoritmo "difícil" e quase sempre nas costuras de integração: um dev-proxy do Vite brigando com o port forwarding do DevContainer, CORS, subir o uvicorn com `--host 0.0.0.0`. Meu histórico de commits é um registro honesto dessas pequenas batalhas — que é exatamente o ponto do Build To Learn.

#### **Resultado**

O resultado é uma v1 funcional: um app local onde o líder da banda planeja um show no modo admin, sobe PDFs que são parseados automaticamente, e cada músico abre a setlist no próprio dispositivo e toca a partir de um visualizador de cifras transponível, sempre aceso e capaz de funcionar offline. A stack que chegou lá:

- **Backend:** Python 3.11 · FastAPI · SQLAlchemy · Alembic · SQLite · pdfplumber
- **Frontend:** React 18 · TypeScript · Vite · Tailwind · Zustand · vite-plugin-pwa
- **Qualidade:** 43 testes verdes, empacotado com Makefile e um setup opcional de DevContainer/Docker

#### **Conclusão**

O BandKit respondeu à sua pergunta: sim, um único app local *consegue* servir tanto o organizador quanto o performer a partir de dados compartilhados, e consegue fazer o trabalho pesado de teoria musical de forma instantânea e correta — desde que você trate o palco como um ambiente de primeira classe e hostil à rede, e deixe o modelo de dados, não a UI, carregar a complexidade do modo duplo.

Mais do que o produto, o valor esteve no desafio: meu primeiro frontend React + TypeScript de verdade, um algoritmo de domínio construído e testado do zero, e engenharia offline para uma restrição genuína. Os próximos passos que estou de olho — sincronização em tempo real entre dispositivos, um auto-scroll estilo teleprompter e OCR para cifras escaneadas — são, cada um, um pequeno "Build To Learn" à espera.

Até a próxima!

*Gostou do conteúdo? Assine para receber atualizações e novos artigos!*
