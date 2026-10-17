-- 500 mil pedidos distribuídos entre 1.000 usuários (dados sintéticos para o benchmark)
INSERT INTO orders (user_id, status, amount, created_at)
SELECT (random() * 999)::int + 1,
       (ARRAY['paid','pending','cancelled','refunded'])[1 + (random() * 3)::int],
       round((random() * 500)::numeric, 2),
       now() - (random() * interval '365 days')
FROM generate_series(1, 500000);
