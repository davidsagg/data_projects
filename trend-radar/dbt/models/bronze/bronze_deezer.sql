{{ config(materialized='view') }}

SELECT * FROM bronze_deezer_artist_weekly
