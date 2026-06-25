-- ============================================================
-- PaperPulse – full reset script
-- Run BEFORE schema.sql. Drops everything this project created.
-- ============================================================

-- 1. Drop tables (CASCADE clears dependent views, FKs, policies, indexes, triggers)
DROP TABLE IF EXISTS public.quota_ledger          CASCADE;
DROP TABLE IF EXISTS public.payment_transactions   CASCADE;
DROP TABLE IF EXISTS public.billing_accounts       CASCADE;
DROP TABLE IF EXISTS public.contribution_votes     CASCADE;
DROP TABLE IF EXISTS public.contributions          CASCADE;
DROP TABLE IF EXISTS public.notifications          CASCADE;
DROP TABLE IF EXISTS public.messages               CASCADE;
DROP TABLE IF EXISTS public.chats                  CASCADE;
DROP TABLE IF EXISTS public.reviews                CASCADE;
DROP TABLE IF EXISTS public.login_logs             CASCADE;
DROP TABLE IF EXISTS public.profiles               CASCADE;

-- 2. Drop view (in case CASCADE above didn't already get it via profiles)
DROP VIEW IF EXISTS public.leaderboard CASCADE;

-- 3. Drop functions (CASCADE drops the triggers attached to them too)
DROP FUNCTION IF EXISTS public.billing_request_downgrade(UUID, public.billing_tier) CASCADE;
DROP FUNCTION IF EXISTS public.billing_apply_payment(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.billing_refund_session(UUID, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.billing_start_session(UUID, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.billing_get_or_create_account(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.next_payos_order_code() CASCADE;
DROP FUNCTION IF EXISTS public.protect_privileged_profile_fields() CASCADE;
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;

-- 4. Drop sequence (only created manually; BIGSERIAL ones drop with their table)
DROP SEQUENCE IF EXISTS public.payos_order_code_seq;

-- 5. Drop enum types
DROP TYPE IF EXISTS public.payment_status;
DROP TYPE IF EXISTS public.payment_type;
DROP TYPE IF EXISTS public.billing_tier;
DROP TYPE IF EXISTS public.contribution_status;
DROP TYPE IF EXISTS public.user_role;

-- 6. Drop the trigger on auth.users explicitly (it's on a table we don't own,
--    so dropping handle_new_user() with CASCADE above should already remove
--    it, but this is a safe no-op if it's already gone).
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- 7. Delete any users created by this project from auth.users.
--    ⚠️ Only run this if admin@gmail.com (and any other users you made via
--    this app) are safe to delete. This wipes Supabase Auth identities, not
--    just app data — there's no undo.
DELETE FROM auth.users WHERE email = 'admin@gmail.com';
-- If you had other test accounts signed up through the app, add them here too, e.g.:
-- DELETE FROM auth.users WHERE email IN ('test1@gmail.com', 'test2@gmail.com');