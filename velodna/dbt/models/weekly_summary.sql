-- Resumo por semana de treino. A semana começa na segunda-feira: é a unidade
-- de periodização do ciclismo, e `date_trunc` já ancora nela — diferente de
-- YEAR/WEEK, que quebra na virada do ano.
SELECT
    CAST(date_trunc('week', started_at) AS DATE) AS week_start,
    COUNT(*)                                     AS activity_count,
    SUM(tss)                                     AS total_tss,
    SUM(distance_m) / 1000.0                     AS total_km,
    SUM(moving_time_s) / 3600.0                  AS total_hours,
    SUM(elevation_gain_m)                        AS total_elevation_m,
    AVG(intensity_factor)                        AS avg_intensity_factor
FROM activities
WHERE tss IS NOT NULL
GROUP BY week_start
ORDER BY week_start DESC
