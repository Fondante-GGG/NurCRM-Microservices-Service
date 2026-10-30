from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0159_investor_investorpayout"),
    ]

    operations = [
        migrations.AddField(
            model_name="salereceiptlink",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salereceiptlink",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
