-- 02_partitions.sql
-- Estrategia de fragmentación horizontal primaria por lista (PARTITION BY LIST)
-- sobre la columna `zone` de `tickets`, mas la politica de replicacion por
-- localidad que ancla cada particion a su nodo geografico (Paso 2 y Paso 3
-- de la guia GA-SUM-03/PE-U3; criterio 2.3).
--
-- Justificacion de la clave de particion: `zone` es el atributo por el que el
-- dominio ACC (Soporte Tecnico ISP) filtra la enorme mayoria de las consultas
-- operativas (un tecnico solo ve/atiende tickets de su propia zona), por lo
-- que particionar por zona maximiza la localidad de acceso: la mayoria de las
-- consultas se resuelven leyendo una sola particion en vez de las tres.
--
-- Ejecutar despues de 01_schema.sql:
--   cockroach sql --insecure --host=localhost:26257 -f 02_partitions.sql

SET DATABASE = ticket_db;

ALTER TABLE tickets PARTITION BY LIST (zone) (
    PARTITION tickets_centro  VALUES IN ('QUEVEDO_CENTRO'),
    PARTITION tickets_norte   VALUES IN ('QUEVEDO_NORTE'),
    PARTITION tickets_sur     VALUES IN ('QUEVEDO_SUR'),
    PARTITION tickets_default VALUES IN (DEFAULT)
);

-- Politica de replicacion: cada particion ancla preferentemente una replica
-- al nodo cuya locality coincide con su zona, pero mantiene num_replicas=3
-- (una copia en cada uno de los 3 nodos) para conservar tolerancia a fallos
-- ante la caida de cualquier nodo individual (ver Paso 3 / criterio 2.4).
ALTER PARTITION tickets_centro OF TABLE tickets
    CONFIGURE ZONE USING num_replicas = 3, constraints = '{"+zone=quevedo-centro": 1}';

ALTER PARTITION tickets_norte OF TABLE tickets
    CONFIGURE ZONE USING num_replicas = 3, constraints = '{"+zone=quevedo-norte": 1}';

ALTER PARTITION tickets_sur OF TABLE tickets
    CONFIGURE ZONE USING num_replicas = 3, constraints = '{"+zone=quevedo-sur": 1}';

-- Verificacion (documentar como tabla booktabs en el informe LaTeX):
--   SHOW PARTITIONS FROM TABLE tickets;
--   SHOW RANGES FROM TABLE tickets;
--   SHOW ZONE CONFIGURATION FOR PARTITION tickets_norte OF TABLE tickets;
