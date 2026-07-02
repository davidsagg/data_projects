{{ config(materialized='table') }}

-- Agrega trend_score médio por gênero por semana.
-- UNNEST do array tags para explodir uma linha por gênero.
-- Filtra gêneros com COUNT(DISTINCT artist_mbid) >= 3.
-- trending_direction: delta do avg_score vs semana anterior.

WITH artist_genres AS (
    SELECT
        mbid   AS artist_mbid,
        UNNEST(tags) AS genre
    FROM {{ ref('silver_artists') }}
    WHERE tags IS NOT NULL AND len(tags) > 0
),

genre_scores AS (
    SELECT
        ag.genre,
        ts.week_start,
        ts.trend_score,
        ts.artist_mbid
    FROM {{ ref('gold_trend_scores') }} ts
    INNER JOIN artist_genres ag ON ag.artist_mbid = ts.artist_mbid
    WHERE ts.trend_score IS NOT NULL
),

genre_weekly AS (
    SELECT
        genre,
        week_start,
        AVG(trend_score)            AS avg_trend_score,
        COUNT(DISTINCT artist_mbid) AS artist_count
    FROM genre_scores
    GROUP BY genre, week_start
    HAVING COUNT(DISTINCT artist_mbid) >= 3
),

with_delta AS (
    SELECT
        genre,
        week_start,
        avg_trend_score,
        artist_count,
        avg_trend_score
            - LAG(avg_trend_score) OVER (PARTITION BY genre ORDER BY week_start)
            AS delta
    FROM genre_weekly
)

SELECT
    genre,
    week_start,
    avg_trend_score,
    artist_count,
    delta,
    CASE
        WHEN delta IS NULL THEN 'stable'
        WHEN delta > 5    THEN 'up'
        WHEN delta < -5   THEN 'down'
        ELSE 'stable'
    END AS trending_direction
FROM with_delta
ORDER BY week_start DESC, avg_trend_score DESC
