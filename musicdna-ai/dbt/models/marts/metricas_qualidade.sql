SELECT
    COUNT(*)                                          AS total_faixas,
    COUNT(CASE WHEN title   != '' THEN 1 END)        AS com_titulo,
    COUNT(CASE WHEN artist  != '' THEN 1 END)        AS com_artista,
    COUNT(CASE WHEN genre   != '' THEN 1 END)        AS com_genero,
    COUNT(CASE WHEN bpm > 0 THEN 1 END)       AS com_bpm,
    ROUND(COUNT(CASE WHEN status='indexed' THEN 1 END)*100.0/COUNT(*),1) AS pct_indexado
FROM catalog
