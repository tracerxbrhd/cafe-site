import uuid
from django.db import migrations


def fill_public_id(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    qs = Order.objects.filter(public_id__isnull=True).only("id")
    for o in qs.iterator():
        o.public_id = uuid.uuid4()
        o.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_public_id"),  # проверь имя предыдущей миграции
    ]

    operations = [
        migrations.RunPython(fill_public_id, migrations.RunPython.noop),
    ]