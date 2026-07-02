SELECT
    YEAR(start_time)  AS year,
    WEEK(start_time)  AS week,
    COUNT(*)          AS activity_count,
    SUM(tss)          AS total_tss,
    SUM(distance_m) / 1000 AS total_km
FROM activities
WHERE tss IS NOT NULL
GROUP BY YEAR(start_time), WEEK(start_time)
ORDER BY year DESC, week DESC
