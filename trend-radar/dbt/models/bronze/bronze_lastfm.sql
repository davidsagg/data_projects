{{ config(materialized='view') }}

SELECT * FROM bronze_lastfm_artist_weekly
