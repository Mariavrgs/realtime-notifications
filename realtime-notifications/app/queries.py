# Agregação feita no banco (usa o índice covering idx_orders_user).
SUMMARY_SQL_PG = """
SELECT status, count(*) AS qty, COALESCE(sum(amount), 0) AS total
FROM orders WHERE user_id = {p} GROUP BY status ORDER BY status
"""
SUMMARY_ASYNCPG = SUMMARY_SQL_PG.format(p="$1")
SUMMARY_PSYCOPG = SUMMARY_SQL_PG.format(p="%s")

# Versão ingênua (para comparação): traz todas as linhas e soma em Python.
NAIVE_SQL = "SELECT * FROM orders WHERE user_id = $1"
