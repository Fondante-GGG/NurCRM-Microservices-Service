# 03.11 front-market: миниатюра фото товара (ProductImage.thumb).
# main_productimage маленькая (~26 тыс. строк); колонка NULL без значения по умолчанию — мгновенно.
# Запускать с DB_PORT=5432 PGOPTIONS="-c lock_timeout=5s" и повторами, как 29.10.
import apps.main.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0171_showcase_p0_1101"),
    ]

    operations = [
        migrations.AddField(
            model_name="productimage",
            name="thumb",
            field=models.ImageField(
                blank=True, max_length=255, null=True,
                upload_to=apps.main.models.product_image_thumb_upload_to,
                verbose_name="Миниатюра (WebP 320px)",
            ),
        ),
    ]
