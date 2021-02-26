# Generated by Django 3.1.7 on 2021-02-26 07:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_more_availability_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='location',
            name='county',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='locations', to='core.county'),
        ),
    ]
