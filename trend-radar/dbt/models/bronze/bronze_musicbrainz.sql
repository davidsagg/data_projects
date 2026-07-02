{{ config(materialized='view') }}

SELECT * FROM bronze_musicbrainz_artist_weekly
