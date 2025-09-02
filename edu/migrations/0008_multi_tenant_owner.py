from django.db import migrations, models
from django.conf import settings

def assign_owner(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[-2], settings.AUTH_USER_MODEL.split('.')[-1])
    Year = apps.get_model('edu', 'Year')
    Subject = apps.get_model('edu', 'Subject')

    user = None
    # اختر أول superuser، ثم أول مستخدم
    try:
        user = User.objects.filter(is_superuser=True).order_by('id').first() or User.objects.order_by('id').first()
    except Exception:
        user = None
    if not user:
        return  # لا يوجد مستخدم — اترك الحقول Nullable موقتًا (ستعالج لاحقًا يدويًا)

    for y in Year.objects.filter(owner__isnull=True):
        y.owner_id = user.id
        y.save(update_fields=['owner'])
    for s in Subject.objects.filter(owner__isnull=True):
        s.owner_id = user.id
        s.save(update_fields=['owner'])

class Migration(migrations.Migration):
    dependencies = [
        ('edu', '0007_remove_weeklyquestion_choice1_and_more'),
    ]

    operations = [
        # 1) إضافة الحقول بشكل Nullable أولًا
        migrations.AddField(
            model_name='year',
            name='owner',
            field=models.ForeignKey(related_name='years', null=True, blank=True, on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='subject',
            name='owner',
            field=models.ForeignKey(related_name='subjects', null=True, blank=True, on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),

        # 2) تعديل فهرس الاسم لإلغاء unique على Subject.name
        migrations.AlterField(
            model_name='subject',
            name='name',
            field=models.CharField(max_length=100),
        ),

        # 3) تعبئة المالك الحالي
        migrations.RunPython(assign_owner, migrations.RunPython.noop),

        # 4) جعل الحقول غير قابلة للإهمال الآن
        migrations.AlterField(
            model_name='year',
            name='owner',
            field=models.ForeignKey(related_name='years', on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='subject',
            name='owner',
            field=models.ForeignKey(related_name='subjects', on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),

        # 5) قيود التفرد الجديدة
        migrations.AlterUniqueTogether(
            name='year',
            unique_together={('owner', 'number')},
        ),
        migrations.AlterUniqueTogether(
            name='subject',
            unique_together={('owner', 'name')},
        ),
    ]

