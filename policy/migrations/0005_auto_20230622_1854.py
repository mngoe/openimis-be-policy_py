# Generated by Django 3.2.19 on 2023-06-22 18:54

import core.fields
import datetime
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('policy', '0004_alter_policy_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='policy',
            name='policy_number',
            field=models.CharField(blank=True, db_column='policyNumber', max_length=50, null=True),
        ),
    ]
