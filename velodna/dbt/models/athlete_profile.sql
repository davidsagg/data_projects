SELECT
    am.date,
    am.ctl,
    am.atl,
    am.tsb,
    am.ftp_w,
    hd.sleep_score,
    hd.hrv_rmssd_ms,
    hd.hrv_status
FROM athlete_metrics am
LEFT JOIN health_daily hd ON am.date = hd.date
ORDER BY am.date DESC
