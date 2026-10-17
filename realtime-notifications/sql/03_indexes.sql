-- Índice "covering": a agregação por usuário é resolvida só pelo índice (index-only scan).
CREATE INDEX idx_orders_user ON orders (user_id) INCLUDE (status, amount);
ANALYZE orders;
