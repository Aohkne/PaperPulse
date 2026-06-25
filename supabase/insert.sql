-- ============================================================
-- PaperPulse – seed data
-- Run AFTER schema.sql.
-- Admin account: admin@gmail.com / Login123@
-- ============================================================

-- 1. Create admin user in auth.users
--    (trigger handle_new_user will auto-create the profile)
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
VALUES (
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
);

-- 2. Ensure profile has role = admin
--    (covers the case where the user already existed before schema was re-created)
INSERT INTO public.profiles (id, email, full_name, role)
SELECT id, 'admin@gmail.com', 'Admin', 'admin'::public.user_role
FROM auth.users
WHERE email = 'admin@gmail.com'
ON CONFLICT (id) DO UPDATE
    SET role = 'admin', full_name = 'Admin';

-- 3. Admin billing account = Unlimited tier (no LR/PDF/Gap cap). Not sample/test
--    data — this is real, deliberate configuration for the one real admin account
--    above. NULL quota = unlimited, same convention as billing_get_or_create_account.
INSERT INTO public.billing_accounts (user_id, tier, subscription_lr_quota, subscription_pdf_quota, subscription_gap_quota)
SELECT id, 'unlimited'::public.billing_tier, NULL, NULL, NULL
FROM auth.users
WHERE email = 'admin@gmail.com'
ON CONFLICT (user_id) DO UPDATE
    SET tier = 'unlimited',
        subscription_lr_quota = NULL,
        subscription_pdf_quota = NULL,
        subscription_gap_quota = NULL;
