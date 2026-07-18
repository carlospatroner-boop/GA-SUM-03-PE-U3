#!/usr/bin/env python3
"""Carga datos sinteticos en ticket_db (PFC ACC — Soporte Tecnico ISP).

Inserta tecnicos y un minimo de 10000 tickets distribuidos ~40/30/30 entre las
tres zonas (QUEVEDO_CENTRO/NORTE/SUR), respetando la fragmentacion horizontal
definida en sql/02_partitions.sql. Requiere que sql/01_schema.sql y
sql/02_partitions.sql ya se hayan ejecutado sobre la base de datos destino.

Uso:
    pip install psycopg2-binary faker
    python seed_data.py --host localhost --port 26257 --rows 20000
"""
import argparse
import random
import uuid
from datetime import timedelta

import psycopg2
import psycopg2.extras
from faker import Faker

ZONES = ["QUEVEDO_CENTRO", "QUEVEDO_NORTE", "QUEVEDO_SUR"]
ZONE_WEIGHTS = [0.4, 0.3, 0.3]
CATEGORIES = ["CONECTIVIDAD", "DNS", "HARDWARE", "CONFIGURACION", "VELOCIDAD"]
PRIORITIES = ["CRITICO", "ALTO", "MEDIO", "BAJO"]
STATUSES = ["NUEVO", "ASIGNADO", "EN_PROGRESO", "RESUELTO", "CERRADO"]
SPECIALTIES = ["CONECTIVIDAD", "DNS", "HARDWARE", "CONFIGURACION", "VELOCIDAD"]

TECHNICIANS_PER_ZONE = 4


def seed_technicians(cur, fake: Faker) -> dict:
    """Crea tecnicos y devuelve {zone: [technician_id, ...]}."""
    by_zone = {zone: [] for zone in ZONES}
    for zone in ZONES:
        for _ in range(TECHNICIANS_PER_ZONE):
            tech_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO technicians (id, full_name, zone, specialty, active) "
                "VALUES (%s, %s, %s, %s, TRUE)",
                (str(tech_id), fake.name(), zone, random.choice(SPECIALTIES)),
            )
            by_zone[zone].append(tech_id)
    return by_zone


def build_ticket_row(fake: Faker, zone: str, technicians_by_zone: dict, assign_prob: float):
    status = random.choice(STATUSES)
    created_at = fake.date_time_between(start_date="-30d", end_date="now")
    sla_deadline = created_at + timedelta(hours=4)

    resolved_at = None
    sla_breached = False
    if status in ("RESUELTO", "CERRADO"):
        # tiempo de resolucion realista: la mayoria dentro del SLA, una cola larga lo incumple
        resolution_minutes = int(random.gammavariate(2.0, 90))
        resolved_at = created_at + timedelta(minutes=resolution_minutes)
        sla_breached = resolved_at > sla_deadline

    technician_id = None
    if status != "NUEVO" and random.random() < assign_prob and technicians_by_zone[zone]:
        technician_id = random.choice(technicians_by_zone[zone])

    return (
        zone,
        str(uuid.uuid4()),
        str(uuid.uuid4()),  # client_id (no hay tabla de clientes en esta practica)
        str(technician_id) if technician_id else None,
        random.choice(CATEGORIES),
        random.choice(PRIORITIES),
        status,
        fake.sentence(nb_words=10),
        created_at,
        sla_deadline,
        resolved_at,
        sla_breached,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=26257)
    parser.add_argument("--database", default="ticket_db")
    parser.add_argument("--user", default="root")
    parser.add_argument("--rows", type=int, default=20000, help="cantidad de tickets a insertar (minimo 10000 exigido por la guia)")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--assign-prob", type=float, default=0.65, help="probabilidad de que un ticket no-NUEVO tenga tecnico asignado")
    parser.add_argument("--seed", type=int, default=42, help="semilla para reproducibilidad")
    parser.add_argument("--truncate", action="store_true", help="vaciar technicians/tickets antes de insertar")
    args = parser.parse_args()

    random.seed(args.seed)
    fake = Faker("es_ES")
    Faker.seed(args.seed)

    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.database, user=args.user,
        sslmode="disable",
    )
    conn.autocommit = True
    cur = conn.cursor()

    if args.truncate:
        print("Vaciando tickets y technicians...")
        cur.execute("TRUNCATE TABLE tickets")
        cur.execute("TRUNCATE TABLE technicians CASCADE")

    print(f"Insertando {TECHNICIANS_PER_ZONE * len(ZONES)} tecnicos...")
    technicians_by_zone = seed_technicians(cur, fake)

    print(f"Insertando {args.rows} tickets (distribucion {ZONE_WEIGHTS} entre {ZONES})...")
    rows_by_zone = random.choices(ZONES, weights=ZONE_WEIGHTS, k=args.rows)

    insert_sql = (
        "INSERT INTO tickets "
        "(zone, id, client_id, technician_id, category, priority, status, "
        " description, created_at, sla_deadline, resolved_at, sla_breached) "
        "VALUES %s"
    )

    batch = []
    inserted = 0
    for zone in rows_by_zone:
        batch.append(build_ticket_row(fake, zone, technicians_by_zone, args.assign_prob))
        if len(batch) >= args.batch_size:
            psycopg2.extras.execute_values(cur, insert_sql, batch, page_size=args.batch_size)
            inserted += len(batch)
            batch = []
            print(f"  {inserted}/{args.rows}", end="\r")
    if batch:
        psycopg2.extras.execute_values(cur, insert_sql, batch, page_size=args.batch_size)
        inserted += len(batch)

    print(f"\nListo: {inserted} tickets insertados.")

    print("Recolectando estadisticas (ANALYZE) para que el optimizador tenga planes representativos...")
    cur.execute("ANALYZE tickets")
    cur.execute("ANALYZE technicians")

    cur.execute("SELECT zone, count(*) FROM tickets GROUP BY zone ORDER BY zone")
    print("Distribucion real por zona:")
    for zone, count in cur.fetchall():
        print(f"  {zone}: {count}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
