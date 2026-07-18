-- 01_schema.sql
-- Esquema del PFC de referencia (ACC — Soporte Técnico ISP).
-- La fragmentación horizontal se aplica aparte, en 02_partitions.sql, para
-- que quede documentada como paso explícito e independiente (Paso 2/2.3 de
-- la guía GA-SUM-03/PE-U3).
--
-- Ejecutar: cockroach sql --insecure --host=localhost:26257 -f 01_schema.sql

CREATE DATABASE IF NOT EXISTS ticket_db;
SET DATABASE = ticket_db;

-- Tabla de técnicos (dimensión pequeña, no particionada)
CREATE TABLE IF NOT EXISTS technicians (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name  STRING NOT NULL,
    zone       STRING NOT NULL CHECK (zone IN ('QUEVEDO_CENTRO', 'QUEVEDO_NORTE', 'QUEVEDO_SUR')),
    specialty  STRING,
    active     BOOL NOT NULL DEFAULT TRUE
);

-- Tabla principal: tickets de soporte técnico. La zona forma parte de la PK
-- para que la fragmentación horizontal (02_partitions.sql) pueda anclar cada
-- partición al nodo correspondiente por localidad.
CREATE TABLE IF NOT EXISTS tickets (
    zone            STRING NOT NULL CHECK (zone IN ('QUEVEDO_CENTRO', 'QUEVEDO_NORTE', 'QUEVEDO_SUR')),
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL,
    technician_id   UUID REFERENCES technicians(id),
    category        STRING,                   -- CONECTIVIDAD | DNS | HARDWARE | CONFIGURACION | VELOCIDAD
    priority        STRING,                   -- CRITICO | ALTO | MEDIO | BAJO
    status          STRING NOT NULL DEFAULT 'NUEVO',
    description     STRING,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    sla_deadline    TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    sla_breached    BOOL DEFAULT FALSE,
    PRIMARY KEY (zone, id)
);

CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets (created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status);

-- Resumen agregado de incidencias de red (respaldo del pipeline de analítica,
-- fuera del alcance de esta práctica; se deja declarada por completitud del
-- dominio del PFC).
CREATE TABLE IF NOT EXISTS network_incidents_summary (
    zone                STRING NOT NULL,
    period_hour         TIMESTAMPTZ NOT NULL,
    incident_type       STRING NOT NULL,
    incident_count      INT8 NOT NULL,
    avg_resolution_min  FLOAT8,
    mttr_min            FLOAT8,
    PRIMARY KEY (zone, period_hour, incident_type)
);

-- Verificacion rapida:
--   SHOW CREATE TABLE tickets;
--   SELECT table_name FROM [SHOW TABLES];
