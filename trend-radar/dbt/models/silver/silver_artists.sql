{{ config(materialized='table') }}

-- Unifica artistas de todas as fontes, deduplica por mbid.
-- Fonte primária: Last.fm (mbid obrigatório).
-- Enriquecimento: MusicBrainz (country, tags, sort_name), Deezer (nb_fan).

WITH lastfm AS (
    SELECT
        mbid,
        artist_name                          AS name,
        chart_rank,
        listeners,
        playcount,
        tags                                 AS lastfm_tags,
        week_start,
        ingested_at
    FROM {{ ref('bronze_lastfm') }}
    WHERE mbid IS NOT NULL
),

mb AS (
    SELECT
        mbid,
        sort_name,
        artist_type,
        gender,
        country,
        area,
        tags                                 AS mb_tags,
        begin_date,
        end_date
    FROM {{ ref('bronze_musicbrainz') }}
),

deezer AS (
    SELECT
        artist_name,
        nb_fan,
        nb_album
    FROM {{ ref('bronze_deezer') }}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY artist_name ORDER BY ingested_at DESC) = 1
),

-- Deduplica Last.fm por mbid, mantendo o registro mais recente
deduped AS (
    SELECT
        mbid,
        name,
        chart_rank,
        listeners,
        playcount,
        lastfm_tags,
        week_start,
        ingested_at
    FROM lastfm
    QUALIFY ROW_NUMBER() OVER (PARTITION BY mbid ORDER BY ingested_at DESC) = 1
),

-- Junta enriquecimentos
enriched AS (
    SELECT
        d.mbid,
        d.name,
        d.chart_rank,
        d.listeners,
        d.playcount,
        d.week_start,
        d.ingested_at,
        -- tags: preferir mb_tags se existirem, senão lastfm_tags; limitar a 5
        CASE
            WHEN mb.mb_tags IS NOT NULL AND len(mb.mb_tags) > 0
                THEN list_slice(mb.mb_tags, 1, 5)
            ELSE list_slice(d.lastfm_tags, 1, 5)
        END                                  AS tags,
        mb.sort_name,
        mb.artist_type,
        mb.gender,
        mb.country,
        mb.area,
        mb.begin_date,
        mb.end_date,
        dz.nb_fan,
        dz.nb_album,
        -- flags de presença por fonte
        TRUE                                 AS source_lastfm,
        mb.mbid IS NOT NULL                  AS source_musicbrainz,
        dz.artist_name IS NOT NULL           AS source_deezer
    FROM deduped d
    LEFT JOIN mb  ON mb.mbid = d.mbid
    LEFT JOIN deezer dz ON lower(dz.artist_name) = lower(d.name)
)

SELECT * FROM enriched
