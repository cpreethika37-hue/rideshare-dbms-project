-- dml.sql : trip lifecycle (request -> accept -> start -> complete / cancel)
-- Run AFTER schema.sql + data.sql.  Everything is rolled back at the end so it is re-runnable.
BEGIN;

-- 1. Rider 7 requests a cab from Koramangala (2) to MG Road (1)
INSERT INTO trip (trip_id, rider_id, pickup_zone, drop_zone, requested_at)
VALUES (900001, 7, 2, 1, '2026-11-02 18:05:00');

-- 2. Driver 3 (vehicle 3) accepts
UPDATE trip SET driver_id = 3, vehicle_id = 3, status = 'ACCEPTED',
                accepted_at = '2026-11-02 18:05:40'
WHERE trip_id = 900001;

-- 3. Trip starts
UPDATE trip SET status = 'ONGOING', started_at = '2026-11-02 18:12:00' WHERE trip_id = 900001;

-- 4. Trip completes -> trg_compute_fare creates the fare row (evening peak => 1.5x surge)
UPDATE trip SET status = 'COMPLETED', ended_at = '2026-11-02 18:41:00',
                distance_km = 8.40, rider_rating = 5
WHERE trip_id = 900001;

SELECT t.trip_id, f.base_amount, f.distance_amount, f.time_amount, f.surge_mult, f.total_amount
FROM trip t JOIN fare f USING (trip_id) WHERE t.trip_id = 900001;

-- 5. Payment for it
INSERT INTO payment (payment_id, trip_id, method, amount, status, paid_at)
SELECT 900001, trip_id, 'UPI', total_amount, 'PAID', '2026-11-02 18:42:00' FROM fare WHERE trip_id = 900001;

-- 6. A second request that the rider cancels before any driver accepts
INSERT INTO trip (trip_id, rider_id, pickup_zone, drop_zone, requested_at)
VALUES (900002, 11, 5, 6, '2026-11-02 08:15:00');
UPDATE trip SET status = 'CANCELLED', cancelled_by = 'RIDER' WHERE trip_id = 900002;

-- 7. Trigger guard: an illegal jump must fail (CANCELLED -> COMPLETED)
SAVEPOINT before_bad;
UPDATE trip SET status = 'COMPLETED' WHERE trip_id = 900002;   -- ERROR expected
ROLLBACK TO SAVEPOINT before_bad;

-- 8. Typical maintenance DML
UPDATE driver  SET is_active = FALSE WHERE driver_id = 45;
UPDATE payment SET status = 'PAID', paid_at = '2026-11-03 10:00:00'
 WHERE status = 'PENDING' AND method = 'CASH';
DELETE FROM payment WHERE status = 'FAILED';

ROLLBACK;   -- change to COMMIT to keep the demo rows
