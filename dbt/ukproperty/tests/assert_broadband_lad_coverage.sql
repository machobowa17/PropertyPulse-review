-- Test: pre-aggregated broadband LAD table must cover at least 300 LADs
SELECT COUNT(*) AS lad_count
FROM core_broadband_lad
HAVING COUNT(*) < 300
