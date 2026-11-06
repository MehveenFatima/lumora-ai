-- 013: BKT parameters fitted from learners' quiz answers
--
-- One row per scope ('global' for now). `adopted` is true when the fit explained the answers
-- clearly better than the default parameters and is therefore used by the live model.
CREATE TABLE IF NOT EXISTS bkt_parameters (
    scope TEXT PRIMARY KEY,
    p_l0 DOUBLE PRECISION NOT NULL,
    p_t DOUBLE PRECISION NOT NULL,
    p_g DOUBLE PRECISION NOT NULL,
    p_s DOUBLE PRECISION NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    sequences INT NOT NULL DEFAULT 0,
    log_likelihood DOUBLE PRECISION,
    default_log_likelihood DOUBLE PRECISION,
    adopted BOOLEAN NOT NULL DEFAULT FALSE,
    fitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE bkt_parameters ENABLE ROW LEVEL SECURITY;
