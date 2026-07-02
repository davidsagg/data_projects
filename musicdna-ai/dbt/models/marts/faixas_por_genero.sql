SELECT
    genre,
    COUNT(*) AS total_faixas,
    AVG(bpm) AS bpm_medio,
    MIN(created_at) AS primeira_indexacao,
    MAX(created_at) AS ultima_indexacao
FROM catalog
WHERE genre IS NOT NULL AND genre != ''
GROUP BY genre
ORDER BY total_faixas DESC
