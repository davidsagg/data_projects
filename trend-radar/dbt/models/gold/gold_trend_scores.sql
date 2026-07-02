{{ config(materialized='table') }}

-- Calcula Trend Score composto por artista por semana.
-- Crescimento = (valor_atual - AVG(4 semanas anteriores))
--               / NULLIF(AVG(4 semanas anteriores), 0) * 100
-- Trend Score = 0.40 * crescimento_lastfm
--             + 0.35 * crescimento_youtube
--             + 0.25 * crescimento_deezer
-- Normalizado 0-100. NULL se menos de 4 semanas de histórico.

WITH windowed AS (
    SELECT
        artist_mbid,
        week_start,
        lastfm_plays,
        youtube_views,
        deezer_fans,
        AVG(lastfm_plays)  OVER w  AS avg_lastfm,
        AVG(youtube_views) OVER w  AS avg_youtube,
        AVG(deezer_fans)   OVER w  AS avg_deezer,
        COUNT(*)           OVER w  AS weeks_in_window
    FROM {{ ref('silver_weekly_plays') }}
    WINDOW w AS (
        PARTITION BY artist_mbid
        ORDER BY week_start
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    )
),

scored AS (
    SELECT
        artist_mbid,
        week_start,
        CASE
            WHEN weeks_in_window < 4 THEN NULL
            ELSE GREATEST(0, LEAST(100,
                    0.40 * (lastfm_plays  - avg_lastfm)  / NULLIF(avg_lastfm,  0) * 100
                  + 0.35 * (youtube_views - avg_youtube) / NULLIF(avg_youtube, 0) * 100
                  + 0.25 * (deezer_fans   - avg_deezer)  / NULLIF(avg_deezer,  0) * 100
                ))
        END AS trend_score,
        CASE WHEN weeks_in_window < 4 THEN NULL
             ELSE GREATEST(0, LEAST(100,
                  0.40 * (lastfm_plays  - avg_lastfm)  / NULLIF(avg_lastfm,  0) * 100))
        END AS score_lastfm,
        CASE WHEN weeks_in_window < 4 THEN NULL
             ELSE GREATEST(0, LEAST(100,
                  0.35 * (youtube_views - avg_youtube) / NULLIF(avg_youtube, 0) * 100))
        END AS score_youtube,
        CASE WHEN weeks_in_window < 4 THEN NULL
             ELSE GREATEST(0, LEAST(100,
                  0.25 * (deezer_fans   - avg_deezer)  / NULLIF(avg_deezer,  0) * 100))
        END AS score_deezer
    FROM windowed
),

with_threshold AS (
    SELECT
        artist_mbid,
        week_start,
        trend_score,
        score_lastfm,
        score_youtube,
        score_deezer,
        SUM(CASE WHEN trend_score > 65 THEN 1 ELSE 0 END)
            OVER (PARTITION BY artist_mbid
                  ORDER BY week_start
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            AS weeks_above_threshold
    FROM scored
)

-- week_start DESC para que fetchone() sem ORDER BY retorne a semana mais recente.
SELECT * FROM with_threshold
ORDER BY week_start DESC, artist_mbid
