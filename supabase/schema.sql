-- ============================================================
-- PaperPulse – Supabase schema
-- Run on a fresh database (tables dropped manually beforehand).
-- ============================================================


-- 1. ENUM (guarded — user_role is preserved across resets alongside profiles)
DO $$ BEGIN
    CREATE TYPE public.user_role AS ENUM ('admin', 'user');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- 2. profiles (IF NOT EXISTS — preserved across resets to keep existing users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID             PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT             NOT NULL,
    full_name   TEXT,
    avatar_url  TEXT,
    role        public.user_role NOT NULL DEFAULT 'user',
    is_banned   BOOLEAN          NOT NULL DEFAULT false,
    banned_at   TIMESTAMPTZ,
    ban_reason  TEXT,
    created_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);


-- 3. login_logs (IF NOT EXISTS — preserved across resets)
CREATE TABLE IF NOT EXISTS public.login_logs (
    id           BIGSERIAL   PRIMARY KEY,
    user_id      UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email        TEXT        NOT NULL,
    event_type   TEXT        NOT NULL DEFAULT 'login',
    logged_in_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address   TEXT
);


-- 4. reviews
-- source_type/content_format/pending_annotations support PDF Agent (pdf-agent_SPEC_2.0.md
-- Step P6) — 'uploaded' reviews come from PDF Agent, 'generated' from Research Agent.
-- query is nullable because an uploaded document has no original research query.
CREATE TABLE public.reviews (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title                TEXT        NOT NULL,
    query                TEXT,
    markdown_content     TEXT        NOT NULL,
    source_type          TEXT        NOT NULL DEFAULT 'generated'
                                     CHECK (source_type IN ('generated', 'uploaded')),
    content_format       TEXT        NOT NULL DEFAULT 'markdown'
                                     CHECK (content_format IN ('markdown', 'tex')),
    pending_annotations  JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reviews_user_created ON public.reviews (user_id, created_at DESC);
CREATE INDEX idx_reviews_title_fts    ON public.reviews USING GIN (to_tsvector('english', title));


-- 5. auto-update updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS profiles_set_updated_at ON public.profiles;
CREATE TRIGGER profiles_set_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER reviews_set_updated_at
    BEFORE UPDATE ON public.reviews
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- 6. auto-create profile on sign-up
--    admin@gmail.com → role = 'admin', others → role = 'user'
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
        CASE WHEN NEW.email = 'admin@gmail.com' THEN 'admin'::public.user_role
             ELSE 'user'::public.user_role END
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- 7. Grant permissions to authenticated role
GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles   TO authenticated;
GRANT SELECT, INSERT                  ON public.login_logs TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE  ON public.reviews    TO authenticated;
GRANT USAGE ON SEQUENCE public.login_logs_id_seq TO authenticated;


-- 8. Row Level Security for reviews
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

CREATE POLICY "reviews_select_own" ON public.reviews
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "reviews_insert_own" ON public.reviews
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "reviews_update_own" ON public.reviews
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "reviews_delete_own" ON public.reviews
    FOR DELETE USING (auth.uid() = user_id);


-- 9. chats
CREATE TABLE IF NOT EXISTS public.chats (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.profiles(id)
                         ON DELETE CASCADE,
  title      text        NOT NULL DEFAULT 'New chat',
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_user_id
  ON public.chats(user_id);

DROP TRIGGER IF EXISTS chats_set_updated_at ON public.chats;
CREATE TRIGGER chats_set_updated_at
  BEFORE UPDATE ON public.chats
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE
  ON public.chats TO authenticated;

ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chats_all_own" ON public.chats
  FOR ALL USING (
    auth.uid() = user_id
  );


-- 10. messages
CREATE TABLE IF NOT EXISTS public.messages (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id        uuid        NOT NULL REFERENCES public.chats(id)
                             ON DELETE CASCADE,
  role           text        NOT NULL
                             CHECK (role IN ('user', 'assistant')),
  content        text        NOT NULL,
  papers_cited   jsonb       NOT NULL DEFAULT '[]',
  verify_result  jsonb       NOT NULL DEFAULT '{}',
  snowball_meta  jsonb       NOT NULL DEFAULT '{}',
  created_at     timestamptz NOT NULL DEFAULT NOW()
);
-- Không có updated_at — messages là immutable sau khi tạo
-- papers_cited  : [{id, title, doi, url, year, authors:[]}]
-- verify_result : {status, claims:[{text,verdict,source_excerpt}]}
-- snowball_meta : {backward:[{id,title,doi}], forward:[{id,title,doi}]}

CREATE INDEX IF NOT EXISTS idx_messages_chat_id
  ON public.messages(chat_id);

GRANT SELECT, INSERT
  ON public.messages TO authenticated;
-- UPDATE/DELETE không cần — messages là immutable

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "messages_all_own_chat" ON public.messages
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id    = messages.chat_id
        AND chats.user_id = auth.uid()
    )
  );


-- 11. notifications
CREATE TABLE IF NOT EXISTS public.notifications (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.profiles(id)
                         ON DELETE CASCADE,
  type       text        NOT NULL
                         CHECK (type IN ('new_paper', 'system')),
  content    text        NOT NULL,
  paper_ref  jsonb       NOT NULL DEFAULT '{}',
  is_read    boolean     NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT NOW()
);
-- paper_ref shape: {id, title, doi, url, abstract_snippet, year}

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
  ON public.notifications(user_id)
  WHERE is_read = false;

GRANT SELECT, UPDATE
  ON public.notifications TO authenticated;
-- INSERT chỉ từ service role (backend) — không GRANT cho authenticated

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "notifications_select_own" ON public.notifications
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "notifications_update_own" ON public.notifications
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "notifications_insert_service" ON public.notifications
  FOR INSERT WITH CHECK (true);


-- 12. Đồng kiến tạo (Community Feedback) — normal_feature_SPEC_2.0.md.
-- 12a extends profiles RLS (needed before 12b, since contributions/votes'
-- policies reference profiles.role for admin checks).

-- 12a. RLS trên profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Cần thấy full_name/avatar_url của người khác cho leaderboard/contribution list
-- (DROP-then-CREATE: profiles is preserved across resets, so its policies persist)
DROP POLICY IF EXISTS "profiles_select_all" ON public.profiles;
CREATE POLICY "profiles_select_all" ON public.profiles
    FOR SELECT USING (true);

DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
CREATE POLICY "profiles_update_own" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Chặn user tự nâng role hoặc tự unban — chỉ admin (qua SECURITY DEFINER) mới đổi được.
-- Backend vẫn dùng service-role key (bypass RLS) cho ban/unban thật — trigger này là
-- lớp phòng thủ thứ 2 nếu sau này có client gọi UPDATE profiles trực tiếp.
CREATE OR REPLACE FUNCTION public.protect_privileged_profile_fields()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'
    ) THEN
        NEW.role       := OLD.role;
        NEW.is_banned  := OLD.is_banned;
        NEW.banned_at  := OLD.banned_at;
        NEW.ban_reason := OLD.ban_reason;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS profiles_protect_privileged_fields ON public.profiles;
CREATE TRIGGER profiles_protect_privileged_fields
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.protect_privileged_profile_fields();


-- 12b. contributions + contribution_votes
CREATE TYPE public.contribution_status AS ENUM ('pending', 'approved', 'rejected');

CREATE TABLE public.contributions (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title            TEXT        NOT NULL,
    content          TEXT        NOT NULL,                 -- markdown
    review_id        UUID        REFERENCES public.reviews(id) ON DELETE SET NULL,  -- optional, gắn vào review đã lưu
    status           public.contribution_status NOT NULL DEFAULT 'pending',
    reviewed_by      UUID        REFERENCES auth.users(id),
    reviewed_at      TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contributions_status_created ON public.contributions (status, created_at DESC);
CREATE INDEX idx_contributions_user           ON public.contributions (user_id);

CREATE TRIGGER contributions_set_updated_at
    BEFORE UPDATE ON public.contributions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.contribution_votes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    contribution_id UUID        NOT NULL REFERENCES public.contributions(id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (contribution_id, user_id)   -- 1 user chỉ vote 1 lần / contribution
);

CREATE INDEX idx_contribution_votes_contribution ON public.contribution_votes (contribution_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.contributions      TO authenticated;
GRANT SELECT                        ON public.contributions      TO anon;
GRANT SELECT, INSERT, DELETE        ON public.contribution_votes TO authenticated;

ALTER TABLE public.contributions ENABLE ROW LEVEL SECURITY;

-- Ai cũng xem được contribution đã approved; chủ + admin xem được cả pending/rejected
CREATE POLICY "contributions_select" ON public.contributions
    FOR SELECT USING (
        status = 'approved'
        OR user_id = auth.uid()
        OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );

-- User chưa bị ban mới được submit; luôn tạo ở status pending
CREATE POLICY "contributions_insert" ON public.contributions
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
        AND NOT EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_banned = true)
    );

-- Chủ chỉ sửa được khi còn pending (tránh sửa nội dung sau khi đã approved)
CREATE POLICY "contributions_update_own_pending" ON public.contributions
    FOR UPDATE USING (user_id = auth.uid() AND status = 'pending');

-- Admin sửa được mọi lúc (để approve/reject)
CREATE POLICY "contributions_update_admin" ON public.contributions
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "contributions_delete" ON public.contributions
    FOR DELETE USING (
        user_id = auth.uid()
        OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );

ALTER TABLE public.contribution_votes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "votes_select_all" ON public.contribution_votes
    FOR SELECT USING (true);

-- Chỉ vote được contribution đã approved, và chưa bị ban
CREATE POLICY "votes_insert" ON public.contribution_votes
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
        AND NOT EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_banned = true)
        AND EXISTS (SELECT 1 FROM public.contributions WHERE id = contribution_id AND status = 'approved')
    );

CREATE POLICY "votes_delete_own" ON public.contribution_votes
    FOR DELETE USING (user_id = auth.uid());

-- Leaderboard (view, không cần bảng riêng — tính trực tiếp từ contributions + contribution_votes)
CREATE OR REPLACE VIEW public.leaderboard AS
SELECT
    p.id  AS user_id,
    p.full_name,
    p.avatar_url,
    COUNT(DISTINCT c.id) AS contributions_count,
    COUNT(v.id)          AS total_votes
FROM public.profiles p
JOIN public.contributions c      ON c.user_id = p.id AND c.status = 'approved'
LEFT JOIN public.contribution_votes v ON v.contribution_id = c.id
GROUP BY p.id, p.full_name, p.avatar_url
ORDER BY total_votes DESC, contributions_count DESC;

GRANT SELECT ON public.leaderboard TO authenticated, anon;


-- 13. Payment / Billing (token.html Draft v4 — token-weighted billing).
-- All three features (Literature Review / PDF Agent / Research Gap) draw from a
-- SINGLE per-tier monthly credit pool. 1 credit = $0.001 of model spend. There
-- is no "quota per lượt" and no top-up: exhaust the pool → upgrade or wait for
-- renewal. Flow per run: gate (balance > 0) before running, then charge the
-- ACTUAL token cost after — so a run can push the balance slightly negative,
-- which simply blocks the NEXT run until renewal (token.html §4).
-- Period reset is done LAZILY inside billing_get_or_create_account() — there is
-- no cron/job-runner in this repo.

CREATE TYPE public.billing_tier AS ENUM ('free', 'plus', 'unlimited');

-- 13a. billing_accounts — one shared credit pool.
CREATE TABLE public.billing_accounts (
    user_id                     UUID            PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    tier                        public.billing_tier NOT NULL DEFAULT 'free',
    tier_started_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    tier_period_end             TIMESTAMPTZ     NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    pending_downgrade_tier      public.billing_tier,
    -- NULL = unlimited tier (soft cap only). Otherwise remaining credits this period.
    subscription_credit_balance NUMERIC(10,3)   DEFAULT 50,
    -- Credits consumed since last reset — drives the "% of monthly budget" UI
    -- and the Unlimited soft-cap comparison (SOFT_CAP_CREDIT = 1500).
    credit_used_this_period     NUMERIC(10,3)   NOT NULL DEFAULT 0,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TRIGGER billing_accounts_set_updated_at
    BEFORE UPDATE ON public.billing_accounts
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

GRANT SELECT ON public.billing_accounts TO authenticated;
-- INSERT/UPDATE only via SECURITY DEFINER functions / service role.

ALTER TABLE public.billing_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "billing_accounts_select_own" ON public.billing_accounts
    FOR SELECT USING (auth.uid() = user_id);


-- 13b. payment_transactions — one row per PayOS checkout attempt.
-- Only subscription upgrades now (top-up removed).
CREATE TYPE public.payment_type AS ENUM ('subscription_upgrade');
CREATE TYPE public.payment_status AS ENUM ('pending', 'paid', 'cancelled', 'expired', 'failed');

-- Seeded from wall-clock time so re-running this after reset.sql never reissues
-- an orderCode PayOS has already seen (its uniqueness check survives a DB wipe).
CREATE SEQUENCE public.payos_order_code_seq START 100000;
SELECT setval('public.payos_order_code_seq', GREATEST(100000, floor(extract(epoch FROM now()))::bigint));

CREATE TABLE public.payment_transactions (
    id                   UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID                NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type                 public.payment_type NOT NULL DEFAULT 'subscription_upgrade',
    tier                 public.billing_tier,           -- the tier being upgraded to
    amount_vnd           INTEGER             NOT NULL,
    payos_order_code     BIGINT              NOT NULL UNIQUE,
    payos_payment_link_id TEXT,
    status               public.payment_status NOT NULL DEFAULT 'pending',
    paid_at              TIMESTAMPTZ,
    applied_at           TIMESTAMPTZ,                   -- idempotency guard for billing_apply_payment
    created_at           TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payment_transactions_user    ON public.payment_transactions (user_id, created_at DESC);
CREATE INDEX idx_payment_transactions_order   ON public.payment_transactions (payos_order_code);

GRANT SELECT ON public.payment_transactions TO authenticated;

ALTER TABLE public.payment_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "payment_transactions_select_own" ON public.payment_transactions
    FOR SELECT USING (auth.uid() = user_id);


-- 13c. quota_ledger — audit trail of every credit charge/reset. `feature` is
-- still recorded so the UI can show a per-feature breakdown, but it no longer
-- separates budgets (single shared pool). delta is in credits (can be fractional).
CREATE TABLE public.quota_ledger (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    feature     TEXT          NOT NULL CHECK (feature IN ('lr', 'pdf', 'gap')),
    delta       NUMERIC(10,3) NOT NULL,
    session_id  TEXT          NOT NULL,
    reason      TEXT          NOT NULL CHECK (reason IN (
                    'session_charge', 'subscription_reset', 'upgrade_reset'
                )),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_quota_ledger_session ON public.quota_ledger (session_id, feature, reason);
CREATE INDEX idx_quota_ledger_user    ON public.quota_ledger (user_id, created_at DESC);

GRANT SELECT ON public.quota_ledger TO authenticated;

ALTER TABLE public.quota_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY "quota_ledger_select_own" ON public.quota_ledger
    FOR SELECT USING (auth.uid() = user_id);


-- 13d. billing_get_or_create_account — lazy init + lazy period reset.
CREATE OR REPLACE FUNCTION public.billing_get_or_create_account(p_user_id UUID)
RETURNS public.billing_accounts LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    acct public.billing_accounts;
    effective_tier public.billing_tier;
BEGIN
    INSERT INTO public.billing_accounts (user_id)
    VALUES (p_user_id)
    ON CONFLICT (user_id) DO NOTHING;

    SELECT * INTO acct FROM public.billing_accounts WHERE user_id = p_user_id FOR UPDATE;

    IF acct.tier_period_end < NOW() THEN
        effective_tier := COALESCE(acct.pending_downgrade_tier, acct.tier);

        UPDATE public.billing_accounts SET
            tier = effective_tier,
            tier_started_at = NOW(),
            tier_period_end = NOW() + INTERVAL '30 days',
            pending_downgrade_tier = NULL,
            subscription_credit_balance = CASE effective_tier
                WHEN 'free' THEN 50 WHEN 'plus' THEN 100 WHEN 'unlimited' THEN NULL END,
            credit_used_this_period = 0
        WHERE user_id = p_user_id
        RETURNING * INTO acct;

        INSERT INTO public.quota_ledger (user_id, feature, delta, session_id, reason)
        VALUES (p_user_id, 'lr', 0, 'reset:' || p_user_id::text, 'subscription_reset');
    END IF;

    RETURN acct;
END;
$$;


-- 13e. billing_gate_session — pre-run gate. Raises QUOTA_EXCEEDED when the pool
-- is empty (balance <= 0). Does NOT deduct — the actual cost is charged after
-- the run via billing_charge_session. Unlimited tier is never blocked.
CREATE OR REPLACE FUNCTION public.billing_gate_session(
    p_user_id UUID, p_feature TEXT, p_session_id TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    acct public.billing_accounts;
BEGIN
    IF p_feature NOT IN ('lr', 'pdf', 'gap') THEN
        RAISE EXCEPTION 'INVALID_FEATURE';
    END IF;

    PERFORM public.billing_get_or_create_account(p_user_id);
    SELECT * INTO acct FROM public.billing_accounts WHERE user_id = p_user_id FOR UPDATE;

    IF acct.subscription_credit_balance IS NULL THEN
        -- unlimited tier — allow, flag soft cap for the caller to log+alert on
        RETURN jsonb_build_object('allowed', true, 'soft_cap_hit', acct.credit_used_this_period > 1500);
    END IF;

    IF acct.subscription_credit_balance <= 0 THEN
        RAISE EXCEPTION 'QUOTA_EXCEEDED';
    END IF;

    RETURN jsonb_build_object('allowed', true, 'soft_cap_hit', false);
END;
$$;


-- 13f. billing_charge_session — deduct the ACTUAL credits a run consumed
-- (p_credits, computed from real token usage). Can drive the balance negative;
-- the next gate call then blocks until renewal. On a system-error run the
-- caller simply doesn't call this (nothing to refund — nothing was charged).
CREATE OR REPLACE FUNCTION public.billing_charge_session(
    p_user_id UUID, p_feature TEXT, p_session_id TEXT, p_credits NUMERIC
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    acct public.billing_accounts;
    v_credits NUMERIC := GREATEST(0, COALESCE(p_credits, 0));
BEGIN
    IF p_feature NOT IN ('lr', 'pdf', 'gap') THEN
        RAISE EXCEPTION 'INVALID_FEATURE';
    END IF;

    PERFORM public.billing_get_or_create_account(p_user_id);
    SELECT * INTO acct FROM public.billing_accounts WHERE user_id = p_user_id FOR UPDATE;

    IF acct.subscription_credit_balance IS NULL THEN
        UPDATE public.billing_accounts SET
            credit_used_this_period = credit_used_this_period + v_credits
            WHERE user_id = p_user_id RETURNING * INTO acct;
    ELSE
        UPDATE public.billing_accounts SET
            subscription_credit_balance = subscription_credit_balance - v_credits,
            credit_used_this_period = credit_used_this_period + v_credits
            WHERE user_id = p_user_id RETURNING * INTO acct;
    END IF;

    INSERT INTO public.quota_ledger (user_id, feature, delta, session_id, reason)
    VALUES (p_user_id, p_feature, -v_credits, p_session_id, 'session_charge');

    RETURN jsonb_build_object(
        'charged', v_credits,
        'balance', acct.subscription_credit_balance,
        'soft_cap_hit', acct.subscription_credit_balance IS NULL AND acct.credit_used_this_period > 1500
    );
END;
$$;


-- 13g. billing_apply_payment — apply a PAID subscription upgrade. Idempotent
-- via applied_at. Resets the credit pool to the new tier's budget (no carryover
-- of the old pool — there's no top-up bucket to hold a remainder anymore).
CREATE OR REPLACE FUNCTION public.billing_apply_payment(p_transaction_id UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    txn public.payment_transactions;
BEGIN
    SELECT * INTO txn FROM public.payment_transactions WHERE id = p_transaction_id FOR UPDATE;

    IF txn.id IS NULL THEN
        RAISE EXCEPTION 'TRANSACTION_NOT_FOUND';
    END IF;

    IF txn.applied_at IS NOT NULL THEN
        RETURN jsonb_build_object('applied', false, 'reason', 'already_applied');
    END IF;

    IF txn.status != 'paid' THEN
        RAISE EXCEPTION 'TRANSACTION_NOT_PAID';
    END IF;

    PERFORM public.billing_get_or_create_account(txn.user_id);

    UPDATE public.billing_accounts SET
        tier = txn.tier,
        tier_started_at = NOW(),
        tier_period_end = NOW() + INTERVAL '30 days',
        pending_downgrade_tier = NULL,
        subscription_credit_balance = CASE txn.tier
            WHEN 'free' THEN 50 WHEN 'plus' THEN 100 WHEN 'unlimited' THEN NULL END,
        credit_used_this_period = 0
        WHERE user_id = txn.user_id;

    INSERT INTO public.quota_ledger (user_id, feature, delta, session_id, reason)
    VALUES (txn.user_id, 'lr', 0, txn.id::text, 'upgrade_reset');

    UPDATE public.payment_transactions SET applied_at = NOW() WHERE id = p_transaction_id;

    RETURN jsonb_build_object('applied', true);
END;
$$;


-- 13h. billing_request_downgrade — no payment; defers to next renewal.
CREATE OR REPLACE FUNCTION public.billing_request_downgrade(p_user_id UUID, p_new_tier public.billing_tier)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    PERFORM public.billing_get_or_create_account(p_user_id);
    UPDATE public.billing_accounts SET pending_downgrade_tier = p_new_tier WHERE user_id = p_user_id;
    RETURN jsonb_build_object('pending_downgrade_tier', p_new_tier);
END;
$$;

-- 13i. next_payos_order_code — fresh unique orderCode via RPC.
CREATE OR REPLACE FUNCTION public.next_payos_order_code()
RETURNS BIGINT LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT nextval('public.payos_order_code_seq');
$$;

-- Revoke the default PUBLIC EXECUTE — these take p_user_id as a plain arg and
-- run server-side only (service-role key), same reasoning as before.
REVOKE EXECUTE ON FUNCTION public.billing_get_or_create_account(UUID) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.billing_gate_session(UUID, TEXT, TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.billing_charge_session(UUID, TEXT, TEXT, NUMERIC) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.billing_apply_payment(UUID) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.billing_request_downgrade(UUID, public.billing_tier) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.next_payos_order_code() FROM PUBLIC;

-- ============================================================================
-- 14. VECTOR STORE (pgvector) — replaces the embedded ChromaDB "papers"
-- collection used by research_agent/services/vector_store.py. Deploy plan:
-- Cloud Run scale-to-zero wipes local disk, so the vector index must live in
-- Supabase instead of ./data/chroma. Same single-shared-keyspace semantics
-- as the old ChromaDB collection (upsert by paper_id, not session-scoped) —
-- this migration only swaps the storage backend, not the data model.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.paper_embeddings (
    paper_id TEXT PRIMARY KEY,
    embedding VECTOR(768),  -- SPECTER v2 dim (S2 batch API) — see vector_store.py upsert_papers() docstring
    title TEXT NOT NULL DEFAULT '',
    year INT,
    citation_count INT,
    abstract TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_paper_embeddings_hnsw
    ON public.paper_embeddings USING hnsw (embedding vector_cosine_ops);

ALTER TABLE public.paper_embeddings ENABLE ROW LEVEL SECURITY;
-- No policy for anon/authenticated — only service_role (used exclusively by
-- backend/module/research_agent/services/vector_store.py) can read/write.

-- 14a. upsert_paper_embedding — single-row upsert via RPC. PostgREST cannot
-- cast a JSON array directly to `vector` on a plain table POST, so writes
-- always go through this function (param typed float8[], cast inside SQL).
CREATE OR REPLACE FUNCTION public.upsert_paper_embedding(
    p_paper_id TEXT,
    p_embedding FLOAT8[],
    p_title TEXT,
    p_year INT,
    p_citation_count INT,
    p_abstract TEXT
) RETURNS VOID LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    INSERT INTO public.paper_embeddings (paper_id, embedding, title, year, citation_count, abstract)
    VALUES (p_paper_id, p_embedding::vector, p_title, p_year, p_citation_count, p_abstract)
    ON CONFLICT (paper_id) DO UPDATE SET
        embedding = EXCLUDED.embedding,
        title = EXCLUDED.title,
        year = EXCLUDED.year,
        citation_count = EXCLUDED.citation_count,
        abstract = EXCLUDED.abstract;
$$;

-- 14b. match_papers — cosine similarity search (same `1 - distance` score
-- shape the old ChromaDB query_by_vector() returned).
CREATE OR REPLACE FUNCTION public.match_papers(
    query_embedding FLOAT8[],
    match_count INT
) RETURNS TABLE(
    paper_id TEXT, title TEXT, year INT, citation_count INT, abstract TEXT, similarity FLOAT8
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT paper_id, title, year, citation_count, abstract,
           1 - (embedding <=> query_embedding::vector) AS similarity
    FROM public.paper_embeddings
    ORDER BY embedding <=> query_embedding::vector
    LIMIT match_count;
$$;

REVOKE EXECUTE ON FUNCTION public.upsert_paper_embedding(TEXT, FLOAT8[], TEXT, INT, INT, TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.match_papers(FLOAT8[], INT) FROM PUBLIC;

-- ============================================================================
-- 15. (removed) SEARCH/LLM RESPONSE CACHE — the `search_cache` table is gone.
-- The LangGraph checkpointer already persists ResearchState per thread_id, and
-- cross-session hit-rate was low (LLM generates different sub_queries each run).
-- ============================================================================

-- ============================================================================
-- 16. LANGGRAPH CHECKPOINTER SCHEMAS — replaces the two SQLite files
-- (./data/checkpoints.db, ./data/pdf_agent_checkpoints.db). Separate Postgres
-- schemas (not just separate tables) so research_agent and pdf_agent thread_id
-- namespaces can never collide, matching the original SQLite-per-domain
-- design intent. Tables inside each schema are created at runtime by
-- AsyncPostgresSaver.setup() — see backend/module/research_agent/graph/graph.py
-- and backend/module/pdf_agent/graph/graph.py.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS research_agent_checkpoints;
CREATE SCHEMA IF NOT EXISTS pdf_agent_checkpoints;

-- ============================================================================
-- 17. GAP DETECTION VECTOR STORES (pgvector) — replaces gap_detection's
-- in-memory ChromaDB EphemeralClient (gap_nim_store.py / gap_specter_store.py,
-- 4096d NIM + 768d SPECTER2). Unlike paper_embeddings (§14, persistent shared
-- cache across all sessions), these two tables are a SESSION-SCOPED candidate
-- pool: cleared via clear_gap_*() RPC at the start of every gap-detection run
-- (retrieval.py rank()) — matching the original EphemeralClient semantics
-- 1:1 (single process-wide store, wiped each call; concurrent gap-detection
-- runs already weren't isolated from each other before this migration either
-- — that's a pre-existing limitation, not a regression).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.gap_nim_embeddings (
    paper_id TEXT PRIMARY KEY,
    embedding VECTOR(4096),  -- NVIDIA nv-embed-v1 output dim
    title TEXT NOT NULL DEFAULT '',
    year INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- No HNSW/IVFFlat index — pgvector caps indexed dimensions at 2000, and 4096 >
-- that limit. Sequential scan is fine here: this table is a small,
-- session-scoped candidate pool (cleared every retrieval.rank() call via
-- clear_gap_nim_embeddings()), not a large persistent corpus like paper_embeddings.
ALTER TABLE public.gap_nim_embeddings ENABLE ROW LEVEL SECURITY;
-- No policy for anon/authenticated — only service_role reads/writes this table.

CREATE TABLE IF NOT EXISTS public.gap_specter_embeddings (
    paper_id TEXT PRIMARY KEY,
    embedding VECTOR(768),  -- SPECTER2 embedding dim
    title TEXT NOT NULL DEFAULT '',
    year INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gap_specter_embeddings_hnsw
    ON public.gap_specter_embeddings USING hnsw (embedding vector_cosine_ops);
ALTER TABLE public.gap_specter_embeddings ENABLE ROW LEVEL SECURITY;
-- No policy for anon/authenticated — only service_role reads/writes this table.

-- 17a. Upserts (single-row, same RPC shape as upsert_paper_embedding §14).
CREATE OR REPLACE FUNCTION public.upsert_gap_nim_embedding(
    p_paper_id TEXT, p_embedding FLOAT8[], p_title TEXT, p_year INT
) RETURNS VOID LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    INSERT INTO public.gap_nim_embeddings (paper_id, embedding, title, year)
    VALUES (p_paper_id, p_embedding::vector, p_title, p_year)
    ON CONFLICT (paper_id) DO UPDATE SET
        embedding = EXCLUDED.embedding, title = EXCLUDED.title, year = EXCLUDED.year;
$$;

CREATE OR REPLACE FUNCTION public.upsert_gap_specter_embedding(
    p_paper_id TEXT, p_embedding FLOAT8[], p_title TEXT, p_year INT
) RETURNS VOID LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    INSERT INTO public.gap_specter_embeddings (paper_id, embedding, title, year)
    VALUES (p_paper_id, p_embedding::vector, p_title, p_year)
    ON CONFLICT (paper_id) DO UPDATE SET
        embedding = EXCLUDED.embedding, title = EXCLUDED.title, year = EXCLUDED.year;
$$;

-- 17b. Nearest-neighbour match — returns cosine DISTANCE (not similarity),
-- ascending = closer first, matching ChromaDB's "hnsw:space": "cosine"
-- distance semantics that gap_nim_store.py/gap_specter_store.py already
-- documented ("ascending distance = closer").
CREATE OR REPLACE FUNCTION public.match_gap_nim_papers(
    query_embedding FLOAT8[], match_count INT
) RETURNS TABLE(paper_id TEXT, distance FLOAT8)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT paper_id, embedding <=> query_embedding::vector AS distance
    FROM public.gap_nim_embeddings
    ORDER BY embedding <=> query_embedding::vector
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION public.match_gap_specter_papers(
    query_embedding FLOAT8[], match_count INT
) RETURNS TABLE(paper_id TEXT, distance FLOAT8)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT paper_id, embedding <=> query_embedding::vector AS distance
    FROM public.gap_specter_embeddings
    ORDER BY embedding <=> query_embedding::vector
    LIMIT match_count;
$$;

-- 17c. Get specific vectors by id (coherence_check.py's _get_specter_vectors
-- — needs the raw float arrays back, not a similarity search). PostgREST
-- can't cast `vector` to JSON cleanly, so cast explicitly inside SQL.
-- pgvector only registers a cast to real[] (float4[]), not float8[]/double
-- precision[] — cast to real[] here (JSON/PostgREST serializes either the
-- same way; float4 precision is plenty for cosine similarity comparisons).
CREATE OR REPLACE FUNCTION public.get_gap_specter_embeddings_by_ids(
    p_paper_ids TEXT[]
) RETURNS TABLE(paper_id TEXT, embedding REAL[])
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT paper_id, embedding::real[] FROM public.gap_specter_embeddings
    WHERE paper_id = ANY(p_paper_ids);
$$;

-- 17d. Clear (truncate) — mirrors EphemeralClient.delete_collection() called
-- at the start of every retrieval.rank() invocation.
CREATE OR REPLACE FUNCTION public.clear_gap_nim_embeddings()
RETURNS VOID LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    DELETE FROM public.gap_nim_embeddings;
$$;

CREATE OR REPLACE FUNCTION public.clear_gap_specter_embeddings()
RETURNS VOID LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    DELETE FROM public.gap_specter_embeddings;
$$;

REVOKE EXECUTE ON FUNCTION public.upsert_gap_nim_embedding(TEXT, FLOAT8[], TEXT, INT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.upsert_gap_specter_embedding(TEXT, FLOAT8[], TEXT, INT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.match_gap_nim_papers(FLOAT8[], INT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.match_gap_specter_papers(FLOAT8[], INT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.get_gap_specter_embeddings_by_ids(TEXT[]) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.clear_gap_nim_embeddings() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.clear_gap_specter_embeddings() FROM PUBLIC;

ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS thread_id text;
ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS feature text NOT NULL DEFAULT 'research';
ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'idle';
ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS summary text;
ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS last_message_at timestamptz;
ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE public.chats ADD COLUMN IF NOT EXISTS topic_id uuid;

CREATE INDEX IF NOT EXISTS idx_chats_user_deleted_last_message
  ON public.chats(user_id, deleted_at, last_message_at DESC, created_at DESC);

-- ============================================================
-- 2. messages extensions
-- ============================================================

ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS seq integer;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS client_message_id text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'done';
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_messages_chat_seq_created
  ON public.messages(chat_id, seq, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_chat_client_message_id
  ON public.messages(chat_id, client_message_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_chat_client_message_id_nonnull
  ON public.messages(chat_id, client_message_id)
  WHERE client_message_id IS NOT NULL;

-- ============================================================
-- 3. notification settings
-- ============================================================

CREATE TABLE IF NOT EXISTS public.notification_settings (
  user_id            uuid        PRIMARY KEY REFERENCES public.profiles(id)
                                 ON DELETE CASCADE,
  pause_all_in_app   boolean     NOT NULL DEFAULT false,
  created_at         timestamptz NOT NULL DEFAULT NOW(),
  updated_at         timestamptz NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS notification_settings_set_updated_at ON public.notification_settings;
CREATE TRIGGER notification_settings_set_updated_at
  BEFORE UPDATE ON public.notification_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE
  ON public.notification_settings TO authenticated;

ALTER TABLE public.notification_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "notification_settings_select_own" ON public.notification_settings;
CREATE POLICY "notification_settings_select_own" ON public.notification_settings
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "notification_settings_insert_own" ON public.notification_settings;
CREATE POLICY "notification_settings_insert_own" ON public.notification_settings
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "notification_settings_update_own" ON public.notification_settings;
CREATE POLICY "notification_settings_update_own" ON public.notification_settings
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "notification_settings_delete_own" ON public.notification_settings;
CREATE POLICY "notification_settings_delete_own" ON public.notification_settings
  FOR DELETE USING (auth.uid() = user_id);

-- ============================================================
-- 4. topic monitoring foundation
-- ============================================================

CREATE TABLE IF NOT EXISTS public.research_topics (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  label            text        NOT NULL,
  normalized_query text        NOT NULL,
  keywords         jsonb       NOT NULL DEFAULT '[]',
  embedding        jsonb,
  created_at       timestamptz NOT NULL DEFAULT NOW(),
  updated_at       timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_research_topics_normalized_query
  ON public.research_topics(normalized_query);

CREATE INDEX IF NOT EXISTS idx_research_topics_label
  ON public.research_topics(label);

CREATE INDEX IF NOT EXISTS idx_research_topics_normalized_query
  ON public.research_topics(normalized_query);

DROP TRIGGER IF EXISTS research_topics_set_updated_at ON public.research_topics;
CREATE TRIGGER research_topics_set_updated_at
  BEFORE UPDATE ON public.research_topics
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS public.user_topic_interests (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid        NOT NULL REFERENCES public.profiles(id)
                               ON DELETE CASCADE,
  topic_id          uuid        NOT NULL REFERENCES public.research_topics(id)
                               ON DELETE CASCADE,
  interest_score    numeric     NOT NULL DEFAULT 0,
  state             text        NOT NULL DEFAULT 'candidate'
                               CHECK (state IN ('candidate', 'auto_watching', 'muted', 'deleted')),
  auto_watch_reason text,
  last_checked_at   timestamptz,
  last_notified_at  timestamptz,
  created_at        timestamptz NOT NULL DEFAULT NOW(),
  updated_at        timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_topic_interests_user_topic
  ON public.user_topic_interests(user_id, topic_id);

CREATE INDEX IF NOT EXISTS idx_user_topic_interests_user_state_score
  ON public.user_topic_interests(user_id, state, interest_score DESC, updated_at DESC);

DROP TRIGGER IF EXISTS user_topic_interests_set_updated_at ON public.user_topic_interests;
CREATE TRIGGER user_topic_interests_set_updated_at
  BEFORE UPDATE ON public.user_topic_interests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE
  ON public.user_topic_interests TO authenticated;

ALTER TABLE public.user_topic_interests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_topic_interests_select_own" ON public.user_topic_interests;
CREATE POLICY "user_topic_interests_select_own" ON public.user_topic_interests
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_topic_interests_insert_own" ON public.user_topic_interests;
CREATE POLICY "user_topic_interests_insert_own" ON public.user_topic_interests
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_topic_interests_update_own" ON public.user_topic_interests;
CREATE POLICY "user_topic_interests_update_own" ON public.user_topic_interests
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_topic_interests_delete_own" ON public.user_topic_interests;
CREATE POLICY "user_topic_interests_delete_own" ON public.user_topic_interests
  FOR DELETE USING (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.papers (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  doi              text,
  arxiv_id         text,
  s2_paper_id      text,
  openalex_id      text,
  pubmed_id        text,
  title            text        NOT NULL,
  abstract         text,
  authors          jsonb       NOT NULL DEFAULT '[]',
  year             integer,
  published_at     timestamptz,
  url              text,
  open_access_pdf  jsonb       NOT NULL DEFAULT '{}',
  source_metadata  jsonb       NOT NULL DEFAULT '{}',
  created_at       timestamptz NOT NULL DEFAULT NOW(),
  updated_at       timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_papers_doi_nonnull
  ON public.papers(doi)
  WHERE doi IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_papers_arxiv_id_nonnull
  ON public.papers(arxiv_id)
  WHERE arxiv_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_papers_s2_paper_id_nonnull
  ON public.papers(s2_paper_id)
  WHERE s2_paper_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_papers_openalex_id_nonnull
  ON public.papers(openalex_id)
  WHERE openalex_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_papers_pubmed_id_nonnull
  ON public.papers(pubmed_id)
  WHERE pubmed_id IS NOT NULL;

DROP TRIGGER IF EXISTS papers_set_updated_at ON public.papers;
CREATE TRIGGER papers_set_updated_at
  BEFORE UPDATE ON public.papers
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS public.topic_paper_matches (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id        uuid        NOT NULL REFERENCES public.research_topics(id)
                              ON DELETE CASCADE,
  paper_id        uuid        NOT NULL REFERENCES public.papers(id)
                              ON DELETE CASCADE,
  vector_score    numeric     NOT NULL DEFAULT 0,
  lexical_score   numeric     NOT NULL DEFAULT 0,
  recency_score   numeric     NOT NULL DEFAULT 0,
  authority_score numeric     NOT NULL DEFAULT 0,
  hybrid_score    numeric     NOT NULL DEFAULT 0,
  reason          text,
  first_seen_at   timestamptz NOT NULL DEFAULT NOW(),
  created_at      timestamptz NOT NULL DEFAULT NOW(),
  updated_at      timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_topic_paper_matches_topic_paper
  ON public.topic_paper_matches(topic_id, paper_id);

CREATE INDEX IF NOT EXISTS idx_topic_paper_matches_topic_score
  ON public.topic_paper_matches(topic_id, hybrid_score DESC, first_seen_at DESC);

DROP TRIGGER IF EXISTS topic_paper_matches_set_updated_at ON public.topic_paper_matches;
CREATE TRIGGER topic_paper_matches_set_updated_at
  BEFORE UPDATE ON public.topic_paper_matches
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS public.notification_events (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.profiles(id)
                         ON DELETE CASCADE,
  topic_id   uuid        NOT NULL REFERENCES public.research_topics(id)
                         ON DELETE CASCADE,
  paper_id   uuid        NOT NULL REFERENCES public.papers(id)
                         ON DELETE CASCADE,
  channel    text        NOT NULL CHECK (channel IN ('in_app', 'email_digest', 'push')),
  status     text        NOT NULL DEFAULT 'created'
                         CHECK (status IN ('created', 'sent', 'skipped', 'failed')),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_events_delivery
  ON public.notification_events(user_id, topic_id, paper_id, channel);

DROP TRIGGER IF EXISTS notification_events_set_updated_at ON public.notification_events;
CREATE TRIGGER notification_events_set_updated_at
  BEFORE UPDATE ON public.notification_events
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.research_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.topic_paper_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_events ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 5. notifications extensions
-- ============================================================

ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS topic_id uuid REFERENCES public.research_topics(id) ON DELETE SET NULL;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS paper_id uuid REFERENCES public.papers(id) ON DELETE SET NULL;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS reason text;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS score numeric;

-- ============================================================
-- 6. chats.topic_id foreign key
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chats_topic_id_fkey'
    ) THEN
        ALTER TABLE public.chats
            ADD CONSTRAINT chats_topic_id_fkey
            FOREIGN KEY (topic_id) REFERENCES public.research_topics(id) ON DELETE SET NULL;
    END IF;
END;
$$;