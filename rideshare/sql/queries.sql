-- queries.sql : analytical queries for RideShare  (PostgreSQL)

-- Q1 Demand: trips requested per hour of day (all zones)
SELECT EXTRACT(HOUR FROM requested_at)::INT AS hour_of_day,
       COUNT(*)                              AS requests,
       COUNT(*) FILTER (WHERE status='COMPLETED') AS completed
FROM trip GROUP BY 1 ORDER BY 1;

-- Q2 Demand by pickup zone and time band
SELECT z.zone_name,
       CASE WHEN h BETWEEN 6 AND 9   THEN '1 Morning peak (6-9)'
            WHEN h BETWEEN 10 AND 16 THEN '2 Midday (10-16)'
            WHEN h BETWEEN 17 AND 20 THEN '3 Evening peak (17-20)'
            ELSE '4 Night (21-5)' END AS time_band,
       COUNT(*) AS requests
FROM (SELECT pickup_zone, EXTRACT(HOUR FROM requested_at)::INT AS h FROM trip) t
JOIN zone z ON z.zone_id = t.pickup_zone
GROUP BY 1,2 ORDER BY 1,2;

-- Q3 Busiest zone for each hour (window function)
SELECT hour_of_day, zone_name, requests
FROM (SELECT zone_name, hour_of_day, requests,
             RANK() OVER (PARTITION BY hour_of_day ORDER BY requests DESC) rk
      FROM v_zone_hour_demand) x
WHERE rk = 1 ORDER BY hour_of_day;

-- Q4 Average fare per vehicle type and per km
SELECT v.vehicle_type, COUNT(*) AS trips,
       ROUND(AVG(f.total_amount),2)                 AS avg_fare,
       ROUND(SUM(f.total_amount)/SUM(t.distance_km),2) AS revenue_per_km
FROM trip t JOIN fare f USING (trip_id) JOIN vehicle v ON v.vehicle_id = t.vehicle_id
GROUP BY v.vehicle_type ORDER BY avg_fare;

-- Q5 Top 10 drivers by earnings, with rating
SELECT driver_id, full_name, completed_trips, gross_earnings, avg_rating
FROM v_driver_performance ORDER BY gross_earnings DESC LIMIT 10;

-- Q6 Driver earnings after 20% platform commission, ranked within vehicle type
SELECT d.full_name, v.vehicle_type,
       ROUND(SUM(f.total_amount)*0.80,0) AS driver_payout,
       RANK() OVER (PARTITION BY v.vehicle_type ORDER BY SUM(f.total_amount) DESC) AS rank_in_type
FROM trip t JOIN fare f USING (trip_id)
JOIN driver d ON d.driver_id = t.driver_id
JOIN vehicle v ON v.vehicle_id = t.vehicle_id
GROUP BY d.full_name, v.vehicle_type
ORDER BY v.vehicle_type, rank_in_type LIMIT 15;

-- Q7 Overall cancellation rate and who cancels
SELECT COUNT(*)                                                   AS requests,
       COUNT(*) FILTER (WHERE status='CANCELLED')                 AS cancelled,
       ROUND(100.0*COUNT(*) FILTER (WHERE status='CANCELLED')/COUNT(*),1) AS cancel_pct,
       COUNT(*) FILTER (WHERE cancelled_by='RIDER')               AS by_rider,
       COUNT(*) FILTER (WHERE cancelled_by='DRIVER')              AS by_driver
FROM trip;

-- Q8 Cancellation rate per zone and hour band (where is supply failing?)
SELECT z.zone_name,
       ROUND(100.0*COUNT(*) FILTER (WHERE t.status='CANCELLED')/COUNT(*),1) AS cancel_pct,
       COUNT(*) AS requests
FROM trip t JOIN zone z ON z.zone_id=t.pickup_zone
GROUP BY z.zone_name ORDER BY cancel_pct DESC;

-- Q9 Drivers with a high cancellation rate AFTER accepting (>= 10% and >= 50 accepted trips)
SELECT d.driver_id, d.full_name,
       COUNT(*) AS accepted_trips,
       COUNT(*) FILTER (WHERE t.cancelled_by='DRIVER') AS driver_cancels,
       ROUND(100.0*COUNT(*) FILTER (WHERE t.cancelled_by='DRIVER')/COUNT(*),1) AS driver_cancel_pct,
       ROUND(AVG(t.rider_rating),2) AS avg_rating
FROM trip t JOIN driver d USING (driver_id)
GROUP BY d.driver_id, d.full_name
HAVING COUNT(*) >= 50
   AND 100.0*COUNT(*) FILTER (WHERE t.cancelled_by='DRIVER')/COUNT(*) >= 10
ORDER BY driver_cancel_pct DESC;

-- Q10 Average rating vs cancellation rate: are bad drivers also cancelling more?
WITH d AS (
  SELECT driver_id, AVG(rider_rating) AS rating,
         100.0*COUNT(*) FILTER (WHERE cancelled_by='DRIVER')/COUNT(*) AS cancel_pct
  FROM trip WHERE driver_id IS NOT NULL GROUP BY driver_id)
SELECT ROUND(CORR(rating, cancel_pct)::numeric,3) AS corr_rating_cancel, COUNT(*) AS drivers FROM d;

-- Q11 Daily revenue with 7-day moving average
SELECT day, revenue,
       ROUND(AVG(revenue) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),0) AS ma7
FROM (SELECT t.ended_at::date AS day, SUM(f.total_amount) AS revenue
      FROM trip t JOIN fare f USING (trip_id) GROUP BY 1) s
ORDER BY day LIMIT 14;

-- Q12 Payment mix and pending cash
SELECT method, COUNT(*) AS payments, ROUND(SUM(amount),0) AS amount,
       COUNT(*) FILTER (WHERE status='PENDING') AS pending
FROM payment GROUP BY method ORDER BY amount DESC;

-- Q13 Surge impact: share of revenue earned under surge
SELECT surge_mult, COUNT(*) AS trips, ROUND(SUM(total_amount),0) AS revenue,
       ROUND(100.0*SUM(total_amount)/SUM(SUM(total_amount)) OVER (),1) AS pct_revenue
FROM fare GROUP BY surge_mult ORDER BY surge_mult;

-- Q14 Most popular origin->destination pairs
SELECT zp.zone_name AS pickup, zd.zone_name AS drop_zone, COUNT(*) AS trips,
       ROUND(AVG(t.distance_km),1) AS avg_km
FROM trip t JOIN zone zp ON zp.zone_id=t.pickup_zone JOIN zone zd ON zd.zone_id=t.drop_zone
WHERE t.status='COMPLETED' AND t.pickup_zone<>t.drop_zone
GROUP BY 1,2 ORDER BY trips DESC LIMIT 8;
