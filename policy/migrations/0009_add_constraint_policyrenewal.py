from django.db import migrations




class Migration(migrations.Migration):


    operations = [
        migrations.RunSQL(
            """
            CREATE UNIQUE INDEX unique_policy_validity_to_null
            ON dbo.tblPolicyRenewals (PolicyID, ValidityTo)
            WHERE ValidityTo IS NULL;
            """,
            reverse_sql="DROP INDEX unique_policy_validity_to_null ON dbo.tblPolicyRenewals;"
        ),
    ]
