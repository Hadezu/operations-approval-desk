from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("desk", "0003_public_demo")]
    operations = [
        migrations.RunSQL(
            sql="""
        CREATE OR REPLACE FUNCTION desk_reject_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND EXISTS (
                SELECT 1 FROM desk_demoworkspace
                WHERE team_id = OLD.team_id AND expires_at <= clock_timestamp()
            ) THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'Approval events are append-only';
        END;
        $$;
        """,
            reverse_sql="""
        CREATE OR REPLACE FUNCTION desk_reject_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Approval events are append-only';
        END;
        $$;
        """,
        )
    ]
