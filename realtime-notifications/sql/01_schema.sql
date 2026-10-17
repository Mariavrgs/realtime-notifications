CREATE TABLE orders (
    id         BIGSERIAL PRIMARY KEY,
    user_id    INT           NOT NULL,
    status     TEXT          NOT NULL,
    amount     NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT now()
);
