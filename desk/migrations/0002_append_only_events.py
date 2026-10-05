from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("desk", "0001_initial")]
    operations = [
        migrations.RunSQL(
            sql="""
        CREATE FUNCTION desk_reject_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Approval events are append-only';
        END;
        $$;
        CREATE TRIGGER desk_event_append_only
        BEFORE UPDATE OR DELETE ON desk_event
        FOR EACH ROW EXECUTE FUNCTION desk_reject_event_mutation();
        """,
            reverse_sql="""
        DROP TRIGGER desk_event_append_only ON desk_event;
        DROP FUNCTION desk_reject_event_mutation();
        """,
        )
    ]
