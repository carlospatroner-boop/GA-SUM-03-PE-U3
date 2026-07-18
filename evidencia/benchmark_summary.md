# Comparativa de rendimiento — cluster (3 nodos) vs. nodo unico

| # | Consulta | Cluster (mediana ms) | Nodo unico (mediana ms) | Factor mejora* |
|---|---|---|---|---|
| 1 | Q1_pk_lookup | 5.00 | 2.00 | 0.40x |
| 2 | Q2_rango_zona_fecha | 26.00 | 8.00 | 0.31x |
| 3 | Q3_agregacion_cruzando_zonas | 16.00 | 11.00 | 0.69x |
| 4 | Q4_groupby_sla | 29.00 | 66.00 | 2.28x |
| 5 | Q5_join_tecnicos | 30.00 | 61.00 | 2.03x |

*factor = tiempo_nodo_unico / tiempo_cluster (>1 = el cluster fue mas rapido).