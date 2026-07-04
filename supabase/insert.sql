-- ============================================================
-- PaperPulse – seed data
-- Run AFTER schema.sql.
-- Admin account: admin@gmail.com / Login123@
--
-- Idempotent: reset.sql now PRESERVES auth.users/profiles, so the user rows may
-- already exist. Each auth.users insert is guarded with WHERE NOT EXISTS (email)
-- so re-running never hits the users_email_partial_key unique violation; the
-- profile + billing_account upserts below then (re)assert the intended config.
-- ============================================================

-- 1. Create admin user in auth.users only if it doesn't already exist
--    (trigger handle_new_user auto-creates the profile on a fresh insert).
INSERT INTO auth.users (
    instance_id, id, aud, role, email,
    encrypted_password,
    email_confirmed_at,
    confirmation_token, recovery_token,
    email_change_token_new, email_change,
    email_change_token_current, email_change_confirm_status,
    phone_change, phone_change_token, reauthentication_token,
    is_super_admin, is_sso_user,
    raw_app_meta_data, raw_user_meta_data,
    last_sign_in_at, created_at, updated_at
)
SELECT
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated', 'authenticated',
    'admin@gmail.com',
    crypt('Login123@', gen_salt('bf')),
    NOW(),
    '', '', '', '', '', 0, '', '', '',
    false, false,
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"Admin"}',
    NOW(), NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'admin@gmail.com');

-- 2. Ensure profile has role = admin (covers a preserved/pre-existing user).
INSERT INTO public.profiles (id, email, full_name, role)
SELECT id, 'admin@gmail.com', 'Admin', 'admin'::public.user_role
FROM auth.users
WHERE email = 'admin@gmail.com'
ON CONFLICT (id) DO UPDATE
    SET role = 'admin', full_name = 'Admin';

-- 3. Admin billing = Unlimited tier (NULL credit balance = no cap), token-weighted
--    billing (single credit pool). Deliberate config for the real admin account.
INSERT INTO public.billing_accounts (user_id, tier, subscription_credit_balance)
SELECT id, 'unlimited'::public.billing_tier, NULL
FROM auth.users
WHERE email = 'admin@gmail.com'
ON CONFLICT (user_id) DO UPDATE
    SET tier = 'unlimited',
        subscription_credit_balance = NULL;

-- 4. Test user 1: userTest1@gmail.com / password123!
INSERT INTO auth.users (
    instance_id, id, aud, role, email,
    encrypted_password,
    email_confirmed_at,
    confirmation_token, recovery_token,
    email_change_token_new, email_change,
    email_change_token_current, email_change_confirm_status,
    phone_change, phone_change_token, reauthentication_token,
    is_super_admin, is_sso_user,
    raw_app_meta_data, raw_user_meta_data,
    last_sign_in_at, created_at, updated_at
)
SELECT
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated', 'authenticated',
    'userTest1@gmail.com',
    crypt('password123!', gen_salt('bf')),
    NOW(),
    '', '', '', '', '', 0, '', '', '',
    false, false,
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"Test User 1"}',
    NOW(), NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'userTest1@gmail.com');

INSERT INTO public.profiles (id, email, full_name, role)
SELECT id, 'userTest1@gmail.com', 'Test User 1', 'user'::public.user_role
FROM auth.users
WHERE email = 'userTest1@gmail.com'
ON CONFLICT (id) DO UPDATE
    SET full_name = 'Test User 1';

INSERT INTO public.billing_accounts (user_id, tier, subscription_credit_balance)
SELECT id, 'unlimited'::public.billing_tier, NULL
FROM auth.users
WHERE email = 'userTest1@gmail.com'
ON CONFLICT (user_id) DO UPDATE
    SET tier = 'unlimited',
        subscription_credit_balance = NULL;

-- 5. Test user 2: userTest2@gmail.com / password123!
INSERT INTO auth.users (
    instance_id, id, aud, role, email,
    encrypted_password,
    email_confirmed_at,
    confirmation_token, recovery_token,
    email_change_token_new, email_change,
    email_change_token_current, email_change_confirm_status,
    phone_change, phone_change_token, reauthentication_token,
    is_super_admin, is_sso_user,
    raw_app_meta_data, raw_user_meta_data,
    last_sign_in_at, created_at, updated_at
)
SELECT
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated', 'authenticated',
    'userTest2@gmail.com',
    crypt('password123!', gen_salt('bf')),
    NOW(),
    '', '', '', '', '', 0, '', '', '',
    false, false,
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"Test User 2"}',
    NOW(), NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'userTest2@gmail.com');

INSERT INTO public.profiles (id, email, full_name, role)
SELECT id, 'userTest2@gmail.com', 'Test User 2', 'user'::public.user_role
FROM auth.users
WHERE email = 'userTest2@gmail.com'
ON CONFLICT (id) DO UPDATE
    SET full_name = 'Test User 2';

INSERT INTO public.billing_accounts (user_id, tier, subscription_credit_balance)
SELECT id, 'unlimited'::public.billing_tier, NULL
FROM auth.users
WHERE email = 'userTest2@gmail.com'
ON CONFLICT (user_id) DO UPDATE
    SET tier = 'unlimited',
        subscription_credit_balance = NULL;
