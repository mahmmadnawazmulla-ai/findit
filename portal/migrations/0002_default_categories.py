from django.db import migrations

NAMES = ["Accessories", "Bags", "Clothing", "Documents", "Electronics", "Keys", "Books & Stationery", "Other"]


def add(apps, schema_editor):
    Category = apps.get_model("portal", "Category")
    for n in NAMES:
        Category.objects.get_or_create(name=n)


class Migration(migrations.Migration):
    dependencies = [("portal", "0001_initial")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
