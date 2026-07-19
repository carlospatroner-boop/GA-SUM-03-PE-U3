# pe-u3-crdb-acc

GA-SUM-03 / PE-U3 --- Práctica Experimental Unidad 3: Implementación y
Verificación de un Clúster de Base de Datos Distribuida con CockroachDB,
aplicado al PFC **ACC --- Soporte Técnico ISP** (Sistema de Gestión de
Solicitudes para Soporte Técnico de Internet).

Asignatura: Aplicaciones Distribuidas (ISR-701) --- UTEQ, período 2026--2027 PPA.

> Este repositorio es independiente del repositorio del PFC del equipo (según
> la Sección 3.1 de la guía, los equipos de esta práctica se conforman de
> forma independiente de los equipos de PFC).

## Integrantes

| Nombre | PFC de origen | Rol en esta práctica |
|---|---|---|
| Aucatoma Celorio, Jhinson Stalyn | AGLS – TiendaTech | Responsable de documentación |
| Alvarez Parraga, Jeremy Alexis | ACC – Soporte Técnico ISP | Responsable de calidad |
| Carpio Mendoza, Carlos José | ACC – Soporte Técnico ISP | Líder de desarrollo |

## Estructura del repositorio

```
pe-u3-crdb-acc/
├── README.md                  -- este archivo
├── docker-compose.yml         -- cluster de 3 nodos CockroachDB
├── sql/
│   ├── 01_schema.sql          -- creacion de BD y tablas (PK, FK, CHECK)
│   ├── 02_partitions.sql      -- PARTITION BY LIST + politica de zona
│   └── 03_queries.sql         -- 5 consultas EXPLAIN ANALYZE
├── scripts/
│   ├── seed_data.py           -- carga >=10000 filas (psycopg2 + faker)
│   └── run_benchmark.py       -- compara cluster vs. nodo unico
├── docs/
│   ├── PE_U3_Informe.tex      -- documento fuente LaTeX
│   ├── PE_U3_Informe.pdf      -- documento compilado
│   └── references.bib         -- bibliografia IEEE (biblatex)
├── evidencia/
│   ├── dashboard.png          -- captura de los 3 nodos LIVE (manual)
│   ├── video_tolerancia.mp4   -- video de la prueba de fallos (manual)
│   ├── resultados.csv         -- datos crudos del benchmark
│   └── benchmark_summary.md   -- tabla resumen del benchmark
└── LICENSE
```

## Cómo reproducir el experimento completo

Requisitos: Docker Desktop con el motor corriendo, Python 3.10+.

```bash
pip install psycopg2-binary faker

# 1. Levantar el cluster de 3 nodos
docker compose up -d
docker exec -it crdb-node1 cockroach init --insecure
docker exec -it crdb-node1 cockroach node status --insecure   # los 3 deben decir is_live=true

# Si el puerto 8080 ya esta ocupado en tu maquina, arranca asi en su lugar:
#   CRDB1_HTTP_PORT=8083 docker compose up -d
# y abre http://localhost:8083 (o el puerto que hayas elegido) en vez de 8080.

# 2. Cargar el esquema y la fragmentacion
docker cp sql/01_schema.sql crdb-node1:/01_schema.sql
docker exec crdb-node1 cockroach sql --insecure -f /01_schema.sql
docker cp sql/02_partitions.sql crdb-node1:/02_partitions.sql
docker exec crdb-node1 cockroach sql --insecure -f /02_partitions.sql

# 3. Sembrar datos (>=10000 filas; por defecto 20000)
python scripts/seed_data.py --host localhost --port 26257 --rows 20000

# Verificar la fragmentacion:
docker exec crdb-node1 cockroach sql --insecure -e \
  "SET DATABASE=ticket_db; SHOW PARTITIONS FROM TABLE tickets; SHOW RANGES FROM TABLE tickets;"
```

### Prueba de tolerancia a fallos

Grabar pantalla (2--5 min, continua) mientras corres esto, mostrando el
dashboard web al mismo tiempo que la terminal:

```bash
docker exec crdb-node1 cockroach sql --insecure -e "SELECT COUNT(*) FROM ticket_db.tickets;"
docker stop crdb-node2
docker exec crdb-node1 cockroach sql --insecure -e "SELECT COUNT(*) FROM ticket_db.tickets;"   # debe responder igual, por quorum 2/3
docker exec crdb-node1 cockroach node status --insecure
# esperar ~30s
docker exec crdb-node1 cockroach sql --insecure -e "SET DATABASE=ticket_db; SHOW RANGES FROM TABLE tickets;"
docker start crdb-node2
docker exec crdb-node1 cockroach node status --insecure   # confirmar que vuelve a is_live=true
```

Guardar el video en `evidencia/video_tolerancia.mp4` y una captura del
dashboard (3 nodos `LIVE`) en `evidencia/dashboard.png`.

### Medición de rendimiento (clúster vs. nodo único)

```bash
# Levantar una instancia de nodo unico en otro puerto, con el mismo esquema y datos
docker run -d --name crdb-single -p 26260:26257 -p 8090:8080 \
  cockroachdb/cockroach:latest-v23.2 start-single-node --insecure --max-offset=4500ms

docker cp sql/01_schema.sql crdb-single:/01_schema.sql
docker exec crdb-single cockroach sql --insecure -f /01_schema.sql
# (no hace falta correr 02_partitions.sql en el nodo unico: la fragmentacion
#  por zona no aporta nada con un solo nodo -- ver docs/PE_U3_Informe.tex)

python scripts/seed_data.py --port 26260 --rows 20000

# Comparar ambos entornos y volcar resultados a evidencia/
python scripts/run_benchmark.py --cluster-port 26257 --single-port 26260 --runs 5

docker rm -f crdb-single   # limpiar cuando termines
```

## Nota sobre el entorno de desarrollo (Windows + Docker Desktop/WSL2)

El `docker-compose.yml` fija `--max-offset=4500ms` (por defecto 500ms) porque
en Windows con Docker Desktop sobre WSL2 el reloj de la VM puede desincronizarse
varios segundos después de que el host sale de suspensión, y CockroachDB
rechaza arrancar si detecta más desfase que `max-offset`. Si el clúster falla
al iniciar con un error de tipo `remote wall time is too far ahead`, ejecuta
`wsl --shutdown` y vuelve a abrir Docker Desktop antes de reintentar. No se
recomienda este valor de `max-offset` en un clúster de producción real.

## Licencia

MIT --- ver [LICENSE](LICENSE).
