
from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('policy', '0007_fix_policy_mutation_name'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE UNIQUE INDEX unique_policy_validity_to_null
            ON [dbo].[tblPolicyRenewals] ([PolicyID], [ValidityTo])
            WHERE [ValidityTo] IS NULL;
            """
            if settings.MSSQL else
            """
            CREATE UNIQUE INDEX IF NOT EXISTS unique_policy_validity_to_null
            ON "tblPolicyRenewals" ("PolicyID", "ValidityTo")
            WHERE "ValidityTo" IS NULL;
            """,
            reverse_sql=(
                """
                DROP INDEX unique_policy_validity_to_null
                ON [dbo].[tblPolicyRenewals];
                """
                if settings.MSSQL else
                """
                DROP INDEX IF EXISTS unique_policy_validity_to_null;
                """
            )
        ),
    ]
