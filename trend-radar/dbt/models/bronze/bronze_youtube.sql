{{ config(materialized='view') }}

SELECT * FROM bronze_youtube_channel_weekly
