# VeloDNA — Entity Relationship Diagram

```mermaid
erDiagram
    athletes {
        UUID id PK
        VARCHAR name
        FLOAT ftp_w
        INTEGER max_hr_bpm
        FLOAT weight_kg
        DATE birth_date
        TIMESTAMP created_at
    }

    activities {
        UUID id PK
        UUID athlete_id FK
        VARCHAR source
        VARCHAR sport_type
        TIMESTAMP started_at
        INTEGER elapsed_time_s
        INTEGER moving_time_s
        FLOAT distance_m
        FLOAT elevation_gain_m
        FLOAT avg_power_w
        FLOAT normalized_power_w
        FLOAT avg_hr_bpm
        FLOAT avg_cadence_rpm
        FLOAT avg_speed_ms
        FLOAT tss
        FLOAT intensity_factor
        FLOAT variability_index
        VARCHAR raw_file_path
        TIMESTAMP created_at
    }

    activity_streams {
        BIGINT id PK
        UUID activity_id FK
        INTEGER time_s
        DOUBLE lat
        DOUBLE lon
        FLOAT altitude_m
        FLOAT distance_m
        FLOAT power_w
        FLOAT hr_bpm
        FLOAT cadence_rpm
        FLOAT speed_ms
        FLOAT temperature_c
        FLOAT left_right_balance
    }

    segments {
        UUID id PK
        VARCHAR name
        DOUBLE start_lat
        DOUBLE start_lon
        DOUBLE end_lat
        DOUBLE end_lon
        FLOAT distance_m
        FLOAT elevation_gain_m
        FLOAT avg_grade_pct
        TIMESTAMP created_at
    }

    segment_efforts {
        UUID id PK
        UUID activity_id FK
        UUID segment_id FK
        UUID athlete_id FK
        TIMESTAMP started_at
        INTEGER elapsed_time_s
        FLOAT avg_power_w
        FLOAT avg_hr_bpm
        FLOAT avg_speed_ms
        BOOLEAN is_pr
        INTEGER rank
    }

    routes {
        UUID id PK
        UUID athlete_id FK
        VARCHAR name
        VARCHAR source_file_path
        FLOAT distance_m
        FLOAT elevation_gain_m
        FLOAT estimated_duration_s
        TIMESTAMP created_at
    }

    route_waypoints {
        BIGINT id PK
        UUID route_id FK
        INTEGER sequence
        DOUBLE lat
        DOUBLE lon
        FLOAT altitude_m
        FLOAT distance_from_start_m
    }

    health_metrics {
        UUID id PK
        UUID athlete_id FK
        DATE date
        FLOAT hrv_rmssd_ms
        INTEGER resting_hr_bpm
        FLOAT sleep_hours
        INTEGER sleep_quality_score
        INTEGER recovery_score
        INTEGER body_battery
        INTEGER stress_level
        VARCHAR source
    }

    training_load {
        UUID id PK
        UUID athlete_id FK
        DATE date
        FLOAT ctl
        FLOAT atl
        FLOAT tsb
        FLOAT daily_tss
    }

    power_zones {
        UUID id PK
        UUID athlete_id FK
        INTEGER zone
        VARCHAR label
        FLOAT min_w
        FLOAT max_w
        DATE effective_from
    }

    hr_zones {
        UUID id PK
        UUID athlete_id FK
        INTEGER zone
        VARCHAR label
        INTEGER min_bpm
        INTEGER max_bpm
        DATE effective_from
    }

    ai_conversations {
        UUID id PK
        UUID athlete_id FK
        UUID session_id
        VARCHAR role
        TEXT content
        VARCHAR model
        TIMESTAMP created_at
    }

    ai_insights {
        UUID id PK
        UUID athlete_id FK
        UUID activity_id FK
        VARCHAR insight_type
        TEXT content
        VARCHAR model
        FLOAT confidence_score
        TIMESTAMP created_at
    }

    athletes ||--o{ activities          : "performs"
    athletes ||--o{ health_metrics      : "tracks"
    athletes ||--o{ training_load       : "accumulates"
    athletes ||--o{ routes              : "saves"
    athletes ||--o{ power_zones         : "configures"
    athletes ||--o{ hr_zones            : "configures"
    athletes ||--o{ ai_conversations    : "chats"
    athletes ||--o{ ai_insights         : "receives"
    athletes ||--o{ segment_efforts     : "attempts"

    activities ||--o{ activity_streams  : "contains"
    activities ||--o{ segment_efforts   : "includes"
    activities ||--o{ ai_insights       : "generates"

    segments   ||--o{ segment_efforts   : "benchmarks"

    routes     ||--o{ route_waypoints   : "defines"
```

## Tabelas — Responsabilidades

| Tabela | Módulo | Descrição |
|---|---|---|
| `athletes` | Core | Perfil único do atleta (FTP, peso, FC máx) |
| `activities` | Training Analytics | Resumo de cada atividade processada |
| `activity_streams` | Training Analytics | Séries temporais brutas (1 row/segundo) |
| `segments` | Route Intelligence | Trechos geográficos de referência |
| `segment_efforts` | Route Intelligence | Performances do atleta em cada segmento |
| `routes` | Route Intelligence | Rotas salvas com traçado completo |
| `route_waypoints` | Route Intelligence | Pontos GPS da rota |
| `health_metrics` | Health Insights | HRV, sono, recuperação por dia |
| `training_load` | Training Analytics | CTL / ATL / TSB diário |
| `power_zones` | Training Analytics | Zonas de potência versionadas por FTP |
| `hr_zones` | Training Analytics | Zonas de FC versionadas |
| `ai_conversations` | AI Coach | Histórico completo de chat |
| `ai_insights` | AI Coach | Insights gerados automaticamente pós-atividade |

## Notas de Design

- `activity_streams` cresce ~3 600 rows/hora de atividade; particionado por `activity_id`.
- `training_load` é recalculado via job diário — não derivado em query.
- `power_zones` e `hr_zones` são versionados por `effective_from` para refletir mudanças de FTP ao longo da temporada.
- `ai_insights.activity_id` é nullable — insights semanais e de recuperação não têm atividade associada.
