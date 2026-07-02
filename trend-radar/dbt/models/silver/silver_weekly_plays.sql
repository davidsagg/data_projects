{{ config(materialized='table') }}

-- Une métricas semanais por (mbid, week_start).
-- Fonte de verdade para mbid: silver_artists (via Last.fm).
-- YouTube e Deezer não têm mbid — resolvidos por artist_name.

WITH artists AS (
    SELECT mbid, name, week_start AS sa_week_start
    FROM {{ ref('silver_artists') }}
),

lastfm AS (
    SELECT
        mbid                                     AS artist_mbid,
        week_start,
        listeners                                AS lastfm_listeners,
        playcount                                AS lastfm_playcount,
        chart_rank                               AS lastfm_chart_rank
    FROM {{ ref('bronze_lastfm') }}
    WHERE mbid IS NOT NULL
),

youtube AS (
    SELECT
        a.mbid                                   AS artist_mbid,
        y.week_start,
        y.subscriber_count                       AS yt_subscriber_count,
        y.view_count                             AS yt_view_count,
        y.weekly_views                           AS yt_weekly_views,
        y.video_count                            AS yt_video_count
    FROM {{ ref('bronze_youtube') }} y
    JOIN artists a
        ON lower(y.artist_name) = lower(a.name)
),

deezer AS (
    SELECT
        a.mbid                                   AS artist_mbid,
        d.week_start,
        d.nb_fan                                 AS dz_nb_fan,
        d.chart_position                         AS dz_chart_position
    FROM {{ ref('bronze_deezer') }} d
    JOIN artists a
        ON lower(d.artist_name) = lower(a.name)
),

-- Todas as combinações (mbid, week_start) observadas em qualquer fonte
all_keys AS (
    SELECT artist_mbid, week_start FROM lastfm
    UNION
    SELECT artist_mbid, week_start FROM youtube
    UNION
    SELECT artist_mbid, week_start FROM deezer
)

SELECT
    k.artist_mbid,
    k.week_start,
    -- Last.fm
    lf.lastfm_listeners,
    lf.lastfm_playcount                          AS lastfm_plays,
    lf.lastfm_chart_rank,
    -- YouTube
    yt.yt_subscriber_count,
    yt.yt_view_count,
    yt.yt_weekly_views                           AS youtube_views,
    yt.yt_video_count,
    -- Deezer
    dz.dz_nb_fan                                 AS deezer_fans,
    dz.dz_chart_position
FROM all_keys k
LEFT JOIN lastfm lf ON lf.artist_mbid = k.artist_mbid AND lf.week_start = k.week_start
LEFT JOIN youtube yt ON yt.artist_mbid = k.artist_mbid AND yt.week_start = k.week_start
LEFT JOIN deezer  dz ON dz.artist_mbid = k.artist_mbid AND dz.week_start = k.week_start
