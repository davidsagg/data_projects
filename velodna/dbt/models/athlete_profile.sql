-- Carga de treino e saúde na mesma linha do dia. `training_load` é a série
-- diária contínua do PMC; `health_metrics` só existe nos dias em que o Garmin
-- sincronizou, por isso o LEFT JOIN parte da carga, não da saúde.
SELECT
    tl.date,
    tl.ctl,
    tl.atl,
    tl.tsb,
    tl.daily_tss,
    hm.hrv_rmssd_ms,
    hm.hrv_status,
    hm.resting_hr_bpm,
    hm.sleep_hours,
    hm.sleep_quality_score,
    hm.body_battery,
    hm.vo2max_estimated
FROM training_load tl
LEFT JOIN health_metrics hm
       ON hm.date = tl.date
      AND hm.athlete_id = tl.athlete_id
ORDER BY tl.date DESC
