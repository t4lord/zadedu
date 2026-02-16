from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('edu', '0008_multi_tenant_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='weeklyquestion',
            name='correct_text',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
