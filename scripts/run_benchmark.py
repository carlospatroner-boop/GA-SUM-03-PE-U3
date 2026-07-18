#!/usr/bin/env python3
"""Compara el rendimiento de sql/03_queries.sql entre el cluster de 3 nodos y
una instancia de nodo unico (Paso 4/criterio 3.3 de la guia GA-SUM-03/PE-U3).

Ejecuta cada una de las 5 consultas con EXPLAIN ANALYZE varias veces en cada
entorno, extrae el "execution time" reportado por CockroachDB y escribe:
  - evidencia/resultados.csv   (una fila por corrida, formato largo)
  - evidencia/benchmark_summary.md  (tabla con la mediana y el factor de mejora)

Requiere que ambos entornos ya tengan el mismo esquema y los mismos datos
cargados (sql/01_schema.sql + sql/02_partitions.sql + seed_data.py).

Uso:
    # nodo unico de comparacion, en otro puerto:
    docker run -d --name crdb-single -p 26260:26257 -p 8090:8080 \\
        cockroachdb/cockroach:latest-v23.2 start-single-node --insecure --max-offset=4500ms

    python run_benchmark.py \\
        --cluster-port 26257 --single-port 26260 --runs 5
"""
import argparse
import csv
import re
import statistics
from pathlib import Path

import psycopg2

QUERIES_FILE = Path(__file__).resolve().parent.parent / "sql" / "03_queries.sql"
EVIDENCIA_DIR = Path(__file__).resolve().parent.parent / "evidencia"

QUERY_LABELS = {
    1: "Q1_pk_lookup",
    2: "Q2_rango_zona_fecha",
    3: "Q3_agregacion_cruzando_zonas",
    4: "Q4_groupby_sla",
    5: "Q5_join_tecnicos",
}

EXEC_TIME_RE = re.compile(r"execution time:\s*([\d.]+)\s*(µs|ms|s)")


def parse_queries(path: Path) -> list[str]:
    """Extrae las 5 sentencias EXPLAIN ANALYZE ... ; del archivo de consultas."""
    text = path.read_text(encoding="utf-8")
    # cada consulta empieza en una linea que arranca con "EXPLAIN ANALYZE" (sin
    # el prefijo de comentario "-- ") y termina en el ';' que le sigue
    blocks = re.findall(r"^(EXPLAIN ANALYZE.*?;)", text, flags=re.DOTALL | re.MULTILINE)
    if len(blocks) != 5:
        raise ValueError(f"Se esperaban 5 consultas en {path}, se encontraron {len(blocks)}")
    return blocks


def run_query_once(cur, sql: str) -> float:
    """Ejecuta una consulta EXPLAIN ANALYZE y devuelve el tiempo de ejecucion en ms."""
    cur.execute(sql)
    rows = cur.fetchall()
    text = "\n".join(str(r[0]) for r in rows)
    match = EXEC_TIME_RE.search(text)
    if not match:
        raise RuntimeError(f"No se pudo extraer 'execution time' de:\n{text[:500]}")
    value, unit = match.groups()
    value = float(value)
    if unit == "µs":
        value /= 1000
    elif unit == "s":
        value *= 1000
    return value


def benchmark_target(dsn: str, queries: list[str], runs: int) -> dict:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ANALYZE tickets")
    cur.execute("ANALYZE technicians")

    results = {i: [] for i in range(1, 6)}
    for run in range(1, runs + 1):
        for i, sql in enumerate(queries, start=1):
            results[i].append(run_query_once(cur, sql))

    cur.close()
    conn.close()
    return results


def write_csv(cluster_results: dict, single_results: dict, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["entorno", "consulta", "run", "tiempo_ms"])
        for entorno, results in (("cluster", cluster_results), ("single", single_results)):
            for qnum, times in results.items():
                for run, t in enumerate(times, start=1):
                    writer.writerow([entorno, QUERY_LABELS[qnum], run, f"{t:.2f}"])


def write_summary(cluster_results: dict, single_results: dict, out_path: Path):
    lines = [
        "# Comparativa de rendimiento — cluster (3 nodos) vs. nodo unico",
        "",
        "| # | Consulta | Cluster (mediana ms) | Nodo unico (mediana ms) | Factor mejora* |",
        "|---|---|---|---|---|",
    ]
    for qnum in range(1, 6):
        c = statistics.median(cluster_results[qnum])
        s = statistics.median(single_results[qnum])
        factor = s / c if c else float("inf")
        lines.append(f"| {qnum} | {QUERY_LABELS[qnum]} | {c:.2f} | {s:.2f} | {factor:.2f}x |")
    lines.append("")
    lines.append("*factor = tiempo_nodo_unico / tiempo_cluster (>1 = el cluster fue mas rapido).")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--cluster-port", type=int, default=26257)
    parser.add_argument("--single-port", type=int, default=26260)
    parser.add_argument("--database", default="ticket_db")
    parser.add_argument("--user", default="root")
    parser.add_argument("--runs", type=int, default=5, help="corridas por consulta (se reporta la mediana)")
    args = parser.parse_args()

    queries = parse_queries(QUERIES_FILE)

    cluster_dsn = f"host={args.host} port={args.cluster_port} dbname={args.database} user={args.user} sslmode=disable"
    single_dsn = f"host={args.host} port={args.single_port} dbname={args.database} user={args.user} sslmode=disable"

    print(f"Corriendo {len(queries)} consultas x {args.runs} veces en el cluster (puerto {args.cluster_port})...")
    cluster_results = benchmark_target(cluster_dsn, queries, args.runs)

    print(f"Corriendo {len(queries)} consultas x {args.runs} veces en el nodo unico (puerto {args.single_port})...")
    single_results = benchmark_target(single_dsn, queries, args.runs)

    write_csv(cluster_results, single_results, EVIDENCIA_DIR / "resultados.csv")
    write_summary(cluster_results, single_results, EVIDENCIA_DIR / "benchmark_summary.md")
    print(f"\nEscrito: {EVIDENCIA_DIR / 'resultados.csv'} y benchmark_summary.md")


if __name__ == "__main__":
    main()
