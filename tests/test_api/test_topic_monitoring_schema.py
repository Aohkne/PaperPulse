from pathlib import Path


def test_schema_contains_topic_monitoring_tables_and_indexes():
    schema = Path("supabase/schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS public.research_topics" in schema
    assert "CREATE TABLE IF NOT EXISTS public.user_topic_interests" in schema
    assert "CREATE TABLE IF NOT EXISTS public.papers" in schema
    assert "CREATE TABLE IF NOT EXISTS public.topic_paper_matches" in schema
    assert "CREATE TABLE IF NOT EXISTS public.notification_events" in schema
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_research_topics_normalized_query" in schema
    assert "CREATE INDEX IF NOT EXISTS idx_user_topic_interests_user_state_score" in schema
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_events_delivery" in schema


def test_schema_extends_notifications_for_topic_linked_alerts():
    schema = Path("supabase/schema.sql").read_text(encoding="utf-8")

    assert "ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS topic_id uuid REFERENCES public.research_topics(id) ON DELETE SET NULL;" in schema
    assert "ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS paper_id uuid REFERENCES public.papers(id) ON DELETE SET NULL;" in schema
    assert "ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS reason text;" in schema
    assert "ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS score numeric;" in schema


def test_schema_protects_user_topic_interests_with_owner_rls():
    schema = Path("supabase/schema.sql").read_text(encoding="utf-8")

    assert "GRANT SELECT, INSERT, UPDATE, DELETE" in schema
    assert 'CREATE POLICY "user_topic_interests_select_own" ON public.user_topic_interests' in schema
    assert 'CREATE POLICY "user_topic_interests_insert_own" ON public.user_topic_interests' in schema
    assert 'CREATE POLICY "user_topic_interests_update_own" ON public.user_topic_interests' in schema
    assert 'CREATE POLICY "user_topic_interests_delete_own" ON public.user_topic_interests' in schema
