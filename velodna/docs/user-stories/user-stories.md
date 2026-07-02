# VeloDNA — User Stories

## Módulo 1: Training Analytics (5 histórias)

---

### US-01 · Upload e visualização de atividade

**Como** ciclista,  
**quero** fazer upload de um arquivo .FIT ou .GPX,  
**para que** eu veja automaticamente o resumo da atividade (distância, tempo, potência média, FC média, TSS).

**Critérios de Aceite:**
- [ ] API aceita multipart/form-data com arquivo .fit ou .gpx (≤ 100 MB)
- [ ] Resposta em < 5 s para arquivos de até 3 horas
- [ ] Retorna: `distance_m`, `elapsed_time_s`, `avg_power_w`, `normalized_power_w`, `avg_hr_bpm`, `tss`, `intensity_factor`
- [ ] Atividade persistida em `activities` + streams em `activity_streams`
- [ ] Retorna 422 com mensagem clara para formato inválido

---

### US-02 · Distribuição de tempo em zonas de potência

**Como** ciclista treinando com medidor de potência,  
**quero** ver quanto tempo passei em cada zona de potência (Z1–Z7),  
**para que** eu avalie se a sessão foi executada conforme o plano.

**Critérios de Aceite:**
- [ ] Zonas calculadas com base no FTP atual do atleta
- [ ] Resultado em segundos e % do tempo total por zona
- [ ] Suporte a zonas de Coggan (7 zonas) e Polarizado (3 zonas)
- [ ] Endpoint: `GET /activities/{id}/power-zones`
- [ ] Inclui gráfico de dados prontos para frontend (array `[{zone, label, seconds, pct}]`)

---

### US-03 · Tracking de carga de treino (CTL / ATL / TSB)

**Como** ciclista em periodização,  
**quero** visualizar minha forma (TSB), fadiga (ATL) e fitness (CTL) ao longo dos últimos 90 dias,  
**para que** eu tome decisões sobre quando intensificar ou recuperar.

**Critérios de Aceite:**
- [ ] CTL calculado com EMA de 42 dias; ATL com EMA de 7 dias; TSB = CTL − ATL
- [ ] Recalculado automaticamente após cada nova atividade
- [ ] Endpoint: `GET /athletes/{id}/training-load?days=90`
- [ ] Alertas quando TSB < −30 (overreaching) ou ramp rate > 8 TSS/semana
- [ ] Exportável como CSV

---

### US-04 · Comparação de performances em atividades similares

**Como** ciclista,  
**quero** comparar minha potência normalizada e TSS entre atividades do mesmo tipo e duração similar,  
**para que** eu identifique evolução ou regressão ao longo da temporada.

**Critérios de Aceite:**
- [ ] Filtros: tipo de atividade, duração (± 20%), período (últimos N dias)
- [ ] Retorna lista ordenada por data com delta % de NP e TSS
- [ ] Destaca PR (melhor NP para a duração) e pior performance
- [ ] Endpoint: `GET /activities/compare?sport=ride&duration=3600&days=180`

---

### US-05 · Exportação de dados de treino

**Como** ciclista analítico,  
**quero** exportar os dados de uma atividade (streams completos) em CSV,  
**para que** eu faça análises externas no Excel ou Python.

**Critérios de Aceite:**
- [ ] Endpoint: `GET /activities/{id}/export?format=csv`
- [ ] CSV inclui: `time_s, lat, lon, altitude_m, power_w, hr_bpm, cadence_rpm, speed_ms`
- [ ] Headers com nome e data da atividade
- [ ] Suporte futuro a JSON (aceita header `Accept: application/json`)

---

## Módulo 2: Route Intelligence (4 histórias)

---

### US-06 · Análise de perfil de elevação de uma rota

**Como** ciclista planejando um percurso,  
**quero** visualizar o perfil de elevação de um arquivo GPX com gradientes por segmento,  
**para que** eu planeje meu esforço e saiba onde estão as subidas críticas.

**Critérios de Aceite:**
- [ ] Endpoint: `POST /routes/analyze` (upload GPX)
- [ ] Retorna: `distance_m`, `elevation_gain_m`, `elevation_loss_m`, `max_grade_pct`, `avg_grade_pct`
- [ ] Array de segmentos de 500 m com `avg_grade_pct`, `vam_potential` e classificação (plano/ondulado/montanhoso)
- [ ] Elevação suavizada (filtro Savitzky-Golay, janela 11 pontos)

---

### US-07 · Identificação e salvamento de segmentos pessoais

**Como** ciclista que treina rotas recorrentes,  
**quero** marcar trechos específicos do meu percurso como segmentos nomeados,  
**para que** o sistema registre automaticamente meu tempo em cada passagem futura.

**Critérios de Aceite:**
- [ ] Endpoint: `POST /segments` com `{name, start_lat, start_lon, end_lat, end_lon}`
- [ ] Matching automático em atividades novas (tolerância GPS: 50 m do ponto de início/fim)
- [ ] Matching roda assincronamente após upload de atividade
- [ ] Registra `segment_efforts` com tempo, NP e FC média
- [ ] PR atualizado automaticamente (menor tempo no segmento)

---

### US-08 · Histórico de performances em um segmento

**Como** ciclista,  
**quero** ver todas as minhas passagens em um segmento com tempos e potências,  
**para que** eu acompanhe minha evolução naquele trecho específico.

**Critérios de Aceite:**
- [ ] Endpoint: `GET /segments/{id}/efforts`
- [ ] Retorna lista ordenada por data com: `elapsed_time_s`, `avg_power_w`, `avg_hr_bpm`, `avg_speed_ms`, `is_pr`
- [ ] Inclui delta % em relação ao PR
- [ ] Paginação: `limit` e `offset`

---

### US-09 · Sugestão de estratégia de pace para uma rota

**Como** ciclista preparando uma gran fondo ou prova,  
**quero** receber uma sugestão de distribuição de potência por segmento de uma rota,  
**para que** eu complete o percurso com o melhor tempo possível sem explodir.

**Critérios de Aceite:**
- [ ] Input: `route_id`, `target_duration_s` (opcional), `ftp_w`
- [ ] Algoritmo de pace baseado em gradiente: potência maior em subidas (≤ 120% FTP), conservadora em plano, recuperação em descidas
- [ ] Retorna por segmento: `target_power_w`, `target_speed_ms`, `estimated_time_s`
- [ ] Endpoint: `POST /routes/{id}/pacing-strategy`

---

## Módulo 3: Health Insights (4 histórias)

---

### US-10 · Registro e tendência de HRV

**Como** ciclista monitorando recuperação,  
**quero** registrar meu HRV diário (RMSSD) e ver a tendência dos últimos 30 dias,  
**para que** eu saiba se meu sistema nervoso autônomo está bem recuperado.

**Critérios de Aceite:**
- [ ] Endpoint: `POST /health/metrics` com `{date, hrv_rmssd_ms, resting_hr_bpm, source}`
- [ ] Sync automático via Garmin Connect se integração ativa
- [ ] Endpoint: `GET /health/hrv-trend?days=30` retorna série temporal + média móvel 7 dias
- [ ] Alerta quando HRV cai > 15% abaixo da média pessoal dos últimos 14 dias

---

### US-11 · Score de recuperação antes do treino

**Como** ciclista,  
**quero** ver um score de recuperação (0–100) ao abrir o app de manhã,  
**para que** eu decida se é dia de treino intenso, leve ou descanso.

**Critérios de Aceite:**
- [ ] Score composto: HRV (40%), qualidade do sono (30%), TSB (20%), FC repouso (10%)
- [ ] Endpoint: `GET /health/recovery-score?date=today`
- [ ] Retorna score + breakdown por componente + recomendação textual (treino intenso / manutenção / descanso)
- [ ] Armazenado em `health_metrics.recovery_score`

---

### US-12 · Correlação entre qualidade do sono e performance

**Como** ciclista,  
**quero** ver a correlação entre minhas métricas de sono e minha potência normalizada nos treinos seguintes,  
**para que** eu entenda o impacto concreto do sono na minha performance.

**Critérios de Aceite:**
- [ ] Endpoint: `GET /health/sleep-performance-correlation?days=90`
- [ ] Calcula correlação de Pearson entre `sleep_hours`/`sleep_quality_score` e NP da atividade do dia seguinte
- [ ] Retorna `r`, `p_value` e interpretação textual ("correlação moderada positiva", etc.)
- [ ] Requer mínimo de 20 pares de observações para resultado válido

---

### US-13 · Alerta de overreaching por carga de treino

**Como** ciclista,  
**quero** receber alertas quando minha carga de treino indicar risco de overreaching,  
**para que** eu previna lesões e síndrome do overtraining.

**Critérios de Aceite:**
- [ ] Trigger: TSB < −30 OR ramp rate > 8 TSS/semana OR HRV suprimido + ATL alto
- [ ] Endpoint: `GET /health/alerts` retorna lista de alertas ativos
- [ ] Cada alerta tem: `type`, `severity` (warning/danger), `message`, `metric_value`, `threshold`
- [ ] Alertas persistidos e não duplicados (deduplicação por tipo + data)

---

## Módulo 4: AI Coach (5 histórias)

---

### US-14 · Chat livre com o coach de IA

**Como** ciclista,  
**quero** conversar em linguagem natural com um coach de IA que conhece meus dados de treino,  
**para que** eu tire dúvidas e receba orientações personalizadas sem precisar de um treinador humano caro.

**Critérios de Aceite:**
- [ ] Endpoint: `POST /coach/chat` com `{session_id, message}`
- [ ] Resposta em streaming (Server-Sent Events)
- [ ] System prompt inclui: FTP, peso, CTL/ATL/TSB atual, últimas 5 atividades, health metrics da semana
- [ ] Histórico da sessão mantido (últimas 20 mensagens) no contexto
- [ ] Modelo padrão: `llama3:latest`; fallback para `mistral:latest`

---

### US-15 · Insight automático pós-atividade

**Como** ciclista,  
**quero** receber um insight gerado por IA logo após o upload de uma atividade,  
**para que** eu entenda o que foi bem, o que foi mal e o que fazer no próximo treino.

**Critérios de Aceite:**
- [ ] Gerado automaticamente após persistência da atividade (background task)
- [ ] Insight cobre: execução vs zonas alvo, pontos de fadiga na atividade, comparação com histórico recente
- [ ] Máximo 250 palavras, tom de coach experiente (direto, sem elogios vagos)
- [ ] Endpoint: `GET /activities/{id}/insight`
- [ ] Armazenado em `ai_insights` com `insight_type="post_activity"`

---

### US-16 · Recomendação de periodização semanal

**Como** ciclista,  
**quero** receber uma sugestão de distribuição de treinos para a próxima semana,  
**para que** eu maximize ganhos respeitando minha capacidade de recuperação atual.

**Critérios de Aceite:**
- [ ] Input: `target_tss_week`, preferências de dias disponíveis
- [ ] AI considera TSB atual, CTL alvo da fase e histórico de volume
- [ ] Retorna plano com 7 dias: tipo de treino, duração estimada e TSS alvo por dia
- [ ] Endpoint: `POST /coach/weekly-plan`
- [ ] Plano armazenado em `ai_insights` com `insight_type="weekly_plan"`

---

### US-17 · Recomendação de estratégia nutricional para treinos longos

**Como** ciclista,  
**quero** perguntar ao coach de IA sobre estratégia de nutrição para um treino longo específico,  
**para que** eu evite bonk e otimize minha energia durante a atividade.

**Critérios de Aceite:**
- [ ] Coach responde com base no TSS estimado do treino, duração e intensidade
- [ ] Resposta inclui: gramas de carboidrato/hora, janela pré-treino, hidratação estimada
- [ ] Coach menciona explicitamente que recomendações são orientação geral (disclaimer obrigatório)
- [ ] Disponível via chat (US-14) com intent detectado automaticamente

---

### US-18 · Alerta de risco de lesão por padrão de carga

**Como** ciclista,  
**quero** que o sistema me avise quando meu padrão de treino sugere risco elevado de lesão por overuse,  
**para que** eu ajuste o volume antes de me machucar.

**Critérios de Aceite:**
- [ ] Análise roda semanalmente via DAG
- [ ] Fatores: ramp rate > 10% semana-a-semana, volume de treino > 120% da média de 4 semanas, TSB < −35
- [ ] AI gera explicação contextualizada do risco (não apenas threshold seco)
- [ ] Endpoint: `GET /coach/insights?type=injury_risk`
- [ ] Notificação armazenada em `ai_insights` com `insight_type="injury_risk"`
