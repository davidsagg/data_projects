SELECT
    job_id,
    title,
    artist,
    genre,
    bpm,
    mood,
    status,
    created_at
FROM catalog
ORDER BY created_at DESC
LIMIT 10
