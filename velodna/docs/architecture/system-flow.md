# VeloDNA — Diagrama de Fluxo do Sistema

## Fluxo Completo

```mermaid
flowchart TD
    subgraph SOURCES["Fontes de Dados"]
        FIT["📁 Arquivo .FIT\n(Garmin/Wahoo)"]
        GPX["📁 Arquivo .GPX\n(Komoot/RideWithGPS)"]
        GARMIN["☁️ Garmin Connect API"]
        STRAVA["☁️ Strava API"]
    end

    subgraph INGESTION["src/ingestion"]
        FIT_P["fit_parser.py\nfitparse"]
        GPX_P["gpx_parser.py\ngpxpy"]
        GARMIN_C["garmin_client.py\ngarminconnect"]
        STRAVA_C["strava_client.py\nstravalib"]
        NORM["normalizer.py\nActivitySchema unificado"]
    end

    subgraph STORAGE["DuckDB — velodna.db"]
        ACT[("activities")]
        STR[("activity_streams")]
        SEG[("segments\nsegment_efforts")]
        ROU[("routes\nroute_waypoints")]
        HLT[("health_metrics")]
        TRL[("training_load")]
        AIC[("ai_conversations\nai_insights")]
    end

    subgraph ANALYTICS["src/analytics"]
        PWR["power_analytics.py\nTSS · NP · IF · VI\nZonas · W/kg"]
        HRV["health_analytics.py\nHRV · Recovery Score\nBody Battery · Correlações"]
        RTE["route_analytics.py\nElevation Profile\nGrade · VAM · Segments"]
        TL["training_load.py\nCTL · ATL · TSB\nRamp Rate"]
    end

    subgraph AI["src/ai"]
        OLLAMA["ollama_client.py\nHTTP → host.docker.internal:11434"]
        CTX["context_builder.py\nMonta prompt com dados do atleta"]
        INS["insight_generator.py\nPós-atividade · Semanal · Recovery"]
    end

    subgraph API["src/api + src/routes"]
        FA["FastAPI app\nmain.py"]
        R_ACT["routes/activities.py\nGET · POST /activities"]
        R_HLT["routes/health.py\nGET · POST /health"]
        R_RTE["routes/routes.py\nGET · POST /routes"]
        R_AI["routes/coach.py\nPOST /coach/chat\nGET /coach/insights"]
        R_HLC["routes/healthcheck.py\nGET /health"]
    end

    subgraph DAGS["dags/ — Airflow DAGs"]
        DAG1["garmin_sync_dag.py\nDiário 06:00"]
        DAG2["training_load_dag.py\nDiário 06:30"]
        DAG3["insight_gen_dag.py\nPós-sync"]
    end

    %% Ingestion flow
    FIT --> FIT_P
    GPX --> GPX_P
    GARMIN --> GARMIN_C
    STRAVA --> STRAVA_C
    FIT_P & GPX_P & GARMIN_C & STRAVA_C --> NORM

    %% Storage flow
    NORM --> ACT
    NORM --> STR
    NORM --> SEG
    NORM --> ROU
    GARMIN_C --> HLT

    %% Analytics flow
    ACT & STR --> PWR
    HLT --> HRV
    ROU & STR --> RTE
    ACT --> TL
    PWR & TL --> TRL

    %% AI flow
    ACT & HLT & TRL --> CTX
    CTX --> OLLAMA
    OLLAMA --> INS
    INS --> AIC

    %% API flow
    FA --> R_ACT & R_HLT & R_RTE & R_AI & R_HLC
    R_ACT --> ACT & STR
    R_HLT --> HLT
    R_RTE --> ROU & SEG
    R_AI --> OLLAMA & AIC

    %% DAGs flow
    DAG1 --> GARMIN_C
    DAG2 --> TL
    DAG3 --> INS

    style SOURCES fill:#1e3a5f,color:#fff
    style INGESTION fill:#1a4731,color:#fff
    style STORAGE fill:#4a1942,color:#fff
    style ANALYTICS fill:#3d2b00,color:#fff
    style AI fill:#3d0000,color:#fff
    style API fill:#003d3d,color:#fff
    style DAGS fill:#2d2d00,color:#fff
```

## Fluxo de uma Atividade (Happy Path)

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant ING as Ingestion
    participant DB as DuckDB
    participant ANA as Analytics
    participant AI as Ollama

    User->>API: POST /activities/upload (.fit)
    API->>ING: parse_fit(file)
    ING-->>API: ActivitySchema (streams + summary)
    API->>DB: INSERT activities + activity_streams
    API->>ANA: compute_metrics(activity_id)
    ANA->>DB: SELECT streams
    ANA-->>DB: UPDATE activities (TSS, NP, IF, zones)
    ANA-->>DB: INSERT training_load (CTL/ATL/TSB)
    API->>AI: generate_insight(activity_id)
    AI->>DB: SELECT activity + athlete context
    AI->>AI: POST /api/generate → Ollama
    AI-->>DB: INSERT ai_insights
    API-->>User: ActivityResponse + insight preview
```

## Fluxo do AI Coach (Chat)

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant CTX as ContextBuilder
    participant DB as DuckDB
    participant OLL as Ollama

    User->>API: POST /coach/chat {"message": "..."}
    API->>CTX: build_context(athlete_id)
    CTX->>DB: SELECT últimas 10 atividades
    CTX->>DB: SELECT training_load (30d)
    CTX->>DB: SELECT health_metrics (7d)
    CTX->>DB: SELECT ai_conversations (session)
    CTX-->>API: system_prompt + history
    API->>OLL: POST host.docker.internal:11434/api/chat
    OLL-->>API: stream response
    API->>DB: INSERT ai_conversations (user + assistant)
    API-->>User: streaming response
```

## Componentes e Tecnologias

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Ingestion | fitparse, gpxpy, stravalib, garminconnect | Parsers nativos por formato |
| Storage | DuckDB | OLAP local, zero infra, queries analíticas rápidas |
| Analytics | pandas, numpy, scipy, scikit-learn | Ecossistema científico Python |
| API | FastAPI + uvicorn | Async, tipagem Pydantic, OpenAPI automático |
| AI | Ollama (llama3 / mistral) | 100% local, sem custo por token, privacidade total |
| Orchestration | Apache Airflow | DAGs versionados, retry, scheduling |
| dbt | dbt-duckdb | Transformações SQL versionadas sobre DuckDB |
