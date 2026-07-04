-- ============================================================
-- PaperPulse – reset script (KEEP user-info tables)
-- Run BEFORE schema.sql. Drops everything this project created
-- EXCEPT the user-identity tables (profiles, login_logs) and the
-- Supabase Auth users — so existing accounts survive a rebuild.
--
-- schema.sql creates profiles/login_logs with IF NOT EXISTS and
-- re-creates their triggers/policies idempotently, so re-running it
-- after this reset will not clobber the preserved rows.
-- ============================================================

-- 1. Drop tables (CASCADE clears dependent views, FKs, policies, indexes,
--    triggers). profiles + login_logs are intentionally NOT dropped.
DROP TABLE IF EXISTS public.quota_ledger          CASCADE;
DROP TABLE IF EXISTS public.payment_transactions   CASCADE;
DROP TABLE IF EXISTS public.billing_accounts       CASCADE;
DROP TABLE IF EXISTS public.contribution_votes     CASCADE;
DROP TABLE IF EXISTS public.contributions          CASCADE;
DROP TABLE IF EXISTS public.notifications          CASCADE;
DROP TABLE IF EXISTS public.messages               CASCADE;
DROP TABLE IF EXISTS public.chats                  CASCADE;
DROP TABLE IF EXISTS public.reviews                CASCADE;
DROP TABLE IF EXISTS public.search_cache           CASCADE;  -- removed table (safe no-op if absent)
DROP TABLE IF EXISTS public.paper_embeddings       CASCADE;
DROP TABLE IF EXISTS public.gap_nim_embeddings     CASCADE;
DROP TABLE IF EXISTS public.gap_specter_embeddings CASCADE;

-- 2. Drop view + leaderboard (recomputed from contributions in schema.sql)
DROP VIEW IF EXISTS public.leaderboard CASCADE;

-- 3. Drop billing / vector-store functions (token-weighted billing names).
DROP FUNCTION IF EXISTS public.billing_request_downgrade(UUID, public.billing_tier) CASCADE;
DROP FUNCTION IF EXISTS public.billing_apply_payment(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.billing_charge_session(UUID, TEXT, TEXT, NUMERIC) CASCADE;
DROP FUNCTION IF EXISTS public.billing_gate_session(UUID, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.billing_get_or_create_account(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.next_payos_order_code() CASCADE;
-- Legacy per-lượt billing functions (safe no-op if this DB predates the migration)
DROP FUNCTION IF EXISTS public.billing_start_session(UUID, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.billing_refund_session(UUID, TEXT, TEXT) CASCADE;

-- 4. Drop sequence (BIGSERIAL ones drop with their table)
DROP SEQUENCE IF EXISTS public.payos_order_code_seq;

-- 5. Drop enum types created by the billing/contribution modules.
DROP TYPE IF EXISTS public.payment_status;
DROP TYPE IF EXISTS public.payment_type;
DROP TYPE IF EXISTS public.billing_tier;
DROP TYPE IF EXISTS public.contribution_status;

-- NOTE: public.user_role, the profiles/login_logs tables, their triggers
-- (set_updated_at, handle_new_user, protect_privileged_profile_fields), and
-- auth.users are intentionally left in place so existing users are preserved.
-- schema.sql re-creates them with IF NOT EXISTS / DROP-then-CREATE guards.
