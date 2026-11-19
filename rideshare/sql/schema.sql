-- =====================================================================
-- RideShare TRANSPORT : Cab Trip and Driver Performance Analytics
-- schema.sql  (PostgreSQL 16)  --  DDL, constraints, triggers, views
-- =====================================================================
DROP VIEW  IF EXISTS v_driver_performance, v_zone_hour_demand CASCADE;
DROP TABLE IF EXISTS payment, fare, trip, vehicle, driver, rider, fare_rate, zone CASCADE;
DROP FUNCTION IF EXISTS fn_trip_guard(), fn_compute_fare() CASCADE;

-- ---------- reference tables ------------------------------------------
CREATE TABLE zone (
    zone_id     SMALLINT     PRIMARY KEY,
    zone_name   VARCHAR(40)  NOT NULL UNIQUE,
    city        VARCHAR(30)  NOT NULL DEFAULT 'Bengaluru',
    centre_lat  NUMERIC(8,5) NOT NULL CHECK (centre_lat  BETWEEN -90  AND 90),
    centre_lng  NUMERIC(8,5) NOT NULL CHECK (centre_lng  BETWEEN -180 AND 180)
);

-- rate card: one row per vehicle type (removes fare rates from vehicle -> 3NF)
CREATE TABLE fare_rate (
    vehicle_type VARCHAR(10)   PRIMARY KEY CHECK (vehicle_type IN ('MINI','SEDAN','SUV')),
    base_fare    NUMERIC(6,2)  NOT NULL CHECK (base_fare >= 0),
    per_km       NUMERIC(6,2)  NOT NULL CHECK (per_km    >= 0),
    per_min      NUMERIC(6,2)  NOT NULL CHECK (per_min   >= 0),
    min_fare     NUMERIC(6,2)  NOT NULL CHECK (min_fare  >= 0)
);

-- ---------- people ----------------------------------------------------
CREATE TABLE rider (
    rider_id    INT          PRIMARY KEY,
    full_name   VARCHAR(60)  NOT NULL,
    phone       CHAR(10)     NOT NULL UNIQUE CHECK (phone ~ '^[6-9][0-9]{9}$'),
    email       VARCHAR(80)  UNIQUE,
    home_zone   SMALLINT     REFERENCES zone(zone_id),
    joined_on   DATE         NOT NULL
);

CREATE TABLE driver (
    driver_id   INT          PRIMARY KEY,
    full_name   VARCHAR(60)  NOT NULL,
    phone       CHAR(10)     NOT NULL UNIQUE CHECK (phone ~ '^[6-9][0-9]{9}$'),
    licence_no  VARCHAR(20)  NOT NULL UNIQUE,
    joined_on   DATE         NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE vehicle (
    vehicle_id    INT          PRIMARY KEY,
    driver_id     INT          NOT NULL REFERENCES driver(driver_id) ON DELETE CASCADE,
    reg_no        VARCHAR(15)  NOT NULL UNIQUE,
    model         VARCHAR(30)  NOT NULL,
    vehicle_type  VARCHAR(10)  NOT NULL REFERENCES fare_rate(vehicle_type),
    seats         SMALLINT     NOT NULL CHECK (seats BETWEEN 2 AND 8)
);

-- ---------- trips -----------------------------------------------------
CREATE TABLE trip (
    trip_id        INT          PRIMARY KEY,
    rider_id       INT          NOT NULL REFERENCES rider(rider_id),
    driver_id      INT          REFERENCES driver(driver_id),     -- NULL until accepted
    vehicle_id     INT          REFERENCES vehicle(vehicle_id),   -- NULL until accepted
    pickup_zone    SMALLINT     NOT NULL REFERENCES zone(zone_id),
    drop_zone      SMALLINT     NOT NULL REFERENCES zone(zone_id),
    requested_at   TIMESTAMP    NOT NULL,
    accepted_at    TIMESTAMP,
    started_at     TIMESTAMP,
    ended_at       TIMESTAMP,
    status         VARCHAR(10)  NOT NULL DEFAULT 'REQUESTED'
                   CHECK (status IN ('REQUESTED','ACCEPTED','ONGOING','COMPLETED','CANCELLED')),
    distance_km    NUMERIC(6,2) CHECK (distance_km > 0),
    cancelled_by   VARCHAR(6)   CHECK (cancelled_by IN ('RIDER','DRIVER')),
    rider_rating   SMALLINT     CHECK (rider_rating BETWEEN 1 AND 5),
    CONSTRAINT ck_time_order CHECK (
        (accepted_at IS NULL OR accepted_at >= requested_at) AND
        (started_at  IS NULL OR started_at  >= accepted_at)  AND
        (ended_at    IS NULL OR ended_at    >= started_at)),
    CONSTRAINT ck_completed_fields CHECK (
        status <> 'COMPLETED' OR
        (driver_id IS NOT NULL AND vehicle_id IS NOT NULL AND started_at IS NOT NULL
         AND ended_at IS NOT NULL AND distance_km IS NOT NULL)),
    CONSTRAINT ck_cancel_reason CHECK ((status = 'CANCELLED') = (cancelled_by IS NOT NULL)),
    CONSTRAINT ck_rating_only_completed CHECK (rider_rating IS NULL OR status = 'COMPLETED')
);
CREATE INDEX ix_trip_requested ON trip (requested_at);
CREATE INDEX ix_trip_driver    ON trip (driver_id, status);
CREATE INDEX ix_trip_pickup    ON trip (pickup_zone, status);

-- ---------- money -----------------------------------------------------
CREATE TABLE fare (                       -- 1 row per COMPLETED trip, filled by trigger
    trip_id         INT           PRIMARY KEY REFERENCES trip(trip_id) ON DELETE CASCADE,
    base_amount     NUMERIC(8,2)  NOT NULL,
    distance_amount NUMERIC(8,2)  NOT NULL,
    time_amount     NUMERIC(8,2)  NOT NULL,
    surge_mult      NUMERIC(3,2)  NOT NULL CHECK (surge_mult >= 1),
    total_amount    NUMERIC(8,2)  NOT NULL CHECK (total_amount > 0)
);

CREATE TABLE payment (
    payment_id  INT           PRIMARY KEY,
    trip_id     INT           NOT NULL UNIQUE REFERENCES fare(trip_id) ON DELETE CASCADE,
    method      VARCHAR(8)    NOT NULL CHECK (method IN ('UPI','CARD','CASH','WALLET')),
    amount      NUMERIC(8,2)  NOT NULL CHECK (amount > 0),
    status      VARCHAR(8)    NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID','PENDING','FAILED')),
    paid_at     TIMESTAMP
);

-- =====================================================================
-- TRIGGER 1  trg_trip_guard  (BEFORE UPDATE on trip)
--   Only legal status moves are allowed and the matching timestamp is
--   stamped automatically.
-- =====================================================================
CREATE FUNCTION fn_trip_guard() RETURNS trigger AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF NOT ( (OLD.status = 'REQUESTED' AND NEW.status IN ('ACCEPTED','CANCELLED'))
          OR (OLD.status = 'ACCEPTED'  AND NEW.status IN ('ONGOING','CANCELLED'))
          OR (OLD.status = 'ONGOING'   AND NEW.status =  'COMPLETED') ) THEN
        RAISE EXCEPTION 'Illegal trip status change % -> % (trip %)',
                        OLD.status, NEW.status, OLD.trip_id;
    END IF;
    IF NEW.status = 'ACCEPTED'  AND NEW.accepted_at IS NULL THEN NEW.accepted_at := now(); END IF;
    IF NEW.status = 'ONGOING'   AND NEW.started_at  IS NULL THEN NEW.started_at  := now(); END IF;
    IF NEW.status = 'COMPLETED' AND NEW.ended_at    IS NULL THEN NEW.ended_at    := now(); END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trip_guard BEFORE UPDATE ON trip
FOR EACH ROW EXECUTE FUNCTION fn_trip_guard();

-- =====================================================================
-- TRIGGER 2  trg_compute_fare  (AFTER INSERT OR UPDATE on trip)
--   When a trip becomes COMPLETED, price it from the rate card:
--     total = GREATEST(min_fare, (base + km*per_km + min*per_min) * surge)
--   surge 1.5x in 08-10h and 17-20h (start hour), 1.2x 22-05h, else 1.0
-- =====================================================================
CREATE FUNCTION fn_compute_fare() RETURNS trigger AS $$
DECLARE
    r        fare_rate%ROWTYPE;
    mins     NUMERIC;
    hr       INT;
    surge    NUMERIC(3,2);
    f_dist   NUMERIC(8,2);
    f_time   NUMERIC(8,2);
BEGIN
    SELECT fr.* INTO r
      FROM vehicle v JOIN fare_rate fr USING (vehicle_type)
     WHERE v.vehicle_id = NEW.vehicle_id;

    mins := EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at)) / 60.0;
    hr   := EXTRACT(HOUR FROM NEW.started_at);
    surge := CASE WHEN hr BETWEEN 8 AND 9 OR hr BETWEEN 17 AND 19 THEN 1.50
                  WHEN hr >= 22 OR hr <= 4                         THEN 1.20
                  ELSE 1.00 END;
    f_dist := ROUND(NEW.distance_km * r.per_km, 2);
    f_time := ROUND(mins * r.per_min, 2);

    INSERT INTO fare(trip_id, base_amount, distance_amount, time_amount, surge_mult, total_amount)
    VALUES (NEW.trip_id, r.base_fare, f_dist, f_time, surge,
            GREATEST(r.min_fare, ROUND((r.base_fare + f_dist + f_time) * surge, 2)))
    ON CONFLICT (trip_id) DO NOTHING;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_compute_fare AFTER INSERT OR UPDATE ON trip
FOR EACH ROW WHEN (NEW.status = 'COMPLETED')
EXECUTE FUNCTION fn_compute_fare();

-- =====================================================================
-- VIEWS
-- =====================================================================
CREATE VIEW v_zone_hour_demand AS
SELECT z.zone_name,
       EXTRACT(HOUR FROM t.requested_at)::INT AS hour_of_day,
       COUNT(*)                                AS requests,
       COUNT(*) FILTER (WHERE t.status = 'COMPLETED') AS completed
FROM trip t JOIN zone z ON z.zone_id = t.pickup_zone
GROUP BY z.zone_name, EXTRACT(HOUR FROM t.requested_at);

CREATE VIEW v_driver_performance AS
SELECT d.driver_id, d.full_name,
       COUNT(*) FILTER (WHERE t.status = 'COMPLETED')                  AS completed_trips,
       COUNT(*) FILTER (WHERE t.status = 'CANCELLED' AND t.cancelled_by = 'DRIVER') AS driver_cancels,
       COALESCE(SUM(f.total_amount), 0)                                AS gross_earnings,
       ROUND(AVG(t.rider_rating), 2)                                   AS avg_rating
FROM driver d
LEFT JOIN trip t ON t.driver_id = d.driver_id
LEFT JOIN fare f ON f.trip_id   = t.trip_id
GROUP BY d.driver_id, d.full_name;
