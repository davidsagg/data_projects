# VeloDNA — User Stories

## Módulo A — Ingestion (US-01 a US-04)

### US-01: Importar atividade de arquivo FIT local
**Como** ciclista,
**quero** fazer upload de um arquivo .FIT local,
**para que** minha atividade seja importada, processada e armazenada automaticamente com todos os streams e métricas derivadas.

### US-02: Importar atividades históricas do Strava
**Como** ciclista com histórico no Strava,
**quero** conectar minha conta e importar minhas atividades passadas,
**para que** eu tenha todo o histórico disponível para análise no VeloDNA.

### US-03: Importar dados de saúde do Garmin Connect
**Como** usuário de dispositivo Garmin,
**quero** sincronizar automaticamente meus dados de saúde diários (HRV, sono, body battery),
**para que** o sistema calcule meu readiness score e correlacione recuperação com performance.

### US-04: Importar rota GPX para análise de prova
**Como** ciclista preparando uma prova,
**quero** fazer upload de um arquivo .GPX,
**para que** o sistema analise o perfil de elevação, segmentos e gere uma estratégia de pacing.

---

## Módulo B — Training Analytics (US-05 a US-09)

### US-05: Visualizar Performance Management Chart (CTL/ATL/TSB)
**Como** ciclista em periodização,
**quero** ver meu gráfico CTL/ATL/TSB dos últimos 90 dias,
**para que** eu tome decisões informadas sobre intensidade e recuperação.

### US-06: Visualizar Power Curve pessoal
**Como** ciclista treinando com medidor de potência,
**quero** ver minha curva de potência máxima por duração (1s a 60min),
**para que** eu identifique minhas capacidades e compare com atividades anteriores.

### US-07: Calcular e detectar FTP automaticamente
**Como** ciclista,
**quero** que o sistema detecte meu FTP a partir das minhas atividades recentes,
**para que** minhas zonas de potência sejam sempre atualizadas sem testes formais frequentes.

### US-08: Analisar zonas de potência de uma atividade
**Como** ciclista,
**quero** ver a distribuição de tempo em cada zona de potência de um treino,
**para que** eu avalie se a sessão foi executada conforme o estímulo planejado.

### US-09: Calcular W Prime e energia anaeróbica
**Como** ciclista,
**quero** visualizar meu W' e seu consumo durante esforços acima do FTP,
**para que** eu entenda minha capacidade anaeróbica e gerencie esforços intensos em provas.

---

## Módulo C — Route Intelligence (US-10 a US-13)

### US-10: Analisar perfil de elevação de uma rota
**Como** ciclista planejando um percurso,
**quero** ver o perfil de elevação detalhado com gradientes por segmento,
**para que** eu conheça as subidas críticas e planeje meu esforço com antecedência.

### US-11: Receber estratégia de pacing para uma prova
**Como** ciclista preparando uma prova,
**quero** receber uma distribuição de potência alvo por segmento da rota,
**para que** eu complete o percurso com o melhor tempo possível sem explodir.

### US-12: Comparar atividade real com rota planejada
**Como** ciclista após uma prova,
**quero** sobrepor minha atividade real com a rota planejada e o pacing sugerido,
**para que** eu veja onde segui ou desviei do plano e aprenda para a próxima vez.

### US-13: Estimar tempo de conclusão de uma rota
**Como** ciclista,
**quero** inserir meu FTP atual e obter uma estimativa de tempo para completar uma rota,
**para que** eu planeje minha logística e defina metas realistas.

---

## Módulo D — Health Insights (US-14 a US-16)

### US-14: Correlacionar qualidade do sono com performance
**Como** ciclista,
**quero** ver a correlação entre minhas métricas de sono e minha potência normalizada no treino seguinte,
**para que** eu entenda o impacto concreto do descanso na minha performance.

### US-15: Acompanhar tendência de HRV e recuperação
**Como** ciclista monitorando recuperação,
**quero** ver a tendência do meu HRV (RMSSD) nos últimos 30 dias com alertas de supressão,
**para que** eu detecte sinais precoces de overtraining antes que virem lesão.

### US-16: Calcular readiness score diário
**Como** ciclista,
**quero** ver um score de prontidão (0–100) ao abrir o app,
**para que** eu decida com base em dados se é dia de treino intenso, leve ou descanso.

---

## Módulo E — AI Coach (US-17 a US-18)

### US-17: Receber análise pós-treino do AI Coach
**Como** ciclista,
**quero** receber uma análise automática da IA após cada atividade importada,
**para que** eu obtenha feedback imediato sobre execução, pontos de fadiga e comparação com histórico.

### US-18: Receber plano de carga semanal do AI Coach
**Como** ciclista em busca de progressão,
**quero** solicitar ao AI Coach um plano de treinos para a semana seguinte,
**para que** eu receba uma distribuição de cargas personalizada ao meu TSB atual e objetivos.
