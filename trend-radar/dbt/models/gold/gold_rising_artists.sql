{{ config(materialized='table') }}

-- Artistas em ascensão: trend_score > 65 por 2+ semanas.
-- Apenas a semana mais recente. Inclui nome, país, gêneros.
-- trending_direction: delta vs semana anterior.

WITH latest_week AS (
    SELECT MAX(week_start) AS max_week
    FROM {{ ref('gold_trend_scores') }}
),

prev_week AS (
    SELECT MAX(week_start) AS prev_week
    FROM {{ ref('gold_trend_scores') }}
    WHERE week_start < (SELECT max_week FROM latest_week)
),

latest_scores AS (
    SELECT ts.*
    FROM {{ ref('gold_trend_scores') }} ts
    INNER JOIN latest_week ON ts.week_start = latest_week.max_week
    WHERE ts.weeks_above_threshold >= 2
),

prev_scores AS (
    SELECT ts.artist_mbid, ts.trend_score AS prev_trend_score
    FROM {{ ref('gold_trend_scores') }} ts
    INNER JOIN prev_week ON ts.week_start = prev_week.prev_week
)

SELECT
    ls.artist_mbid,
    ls.week_start,
    ls.trend_score,
    ls.score_lastfm,
    ls.score_youtube,
    ls.score_deezer,
    ls.weeks_above_threshold,
    sa.name,
    sa.country,
    sa.tags                                                  AS genres,
    CASE
        WHEN (ls.trend_score - ps.prev_trend_score) > 5  THEN 'up'
        WHEN (ls.trend_score - ps.prev_trend_score) < -5 THEN 'down'
        ELSE 'stable'
    END                                                      AS trending_direction,
    ROW_NUMBER() OVER (ORDER BY ls.trend_score DESC)         AS rank_da_semana
FROM latest_scores ls
LEFT JOIN prev_scores  ps ON ps.artist_mbid = ls.artist_mbid
LEFT JOIN {{ ref('silver_artists') }} sa ON sa.mbid = ls.artist_mbid
LIMIT 500  -- máximo de artistas monitorados por semana
