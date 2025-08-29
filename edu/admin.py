from django.contrib import admin, messages
from django.conf import settings
from django.apps import apps

from .models import Year, Term, Subject, SubjectOffering, Lesson, LessonContent, Question


admin.site.register(Lesson)
admin.site.register(LessonContent)
admin.site.register(Question)

@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    list_display = ('id', 'number')
    list_filter = ('number',)

OFFERING_MODEL_NAME = "Offering"  # أو "SubjectOffering" أو None

@admin.action(description="تطبيق المناهج الافتراضية (7 مواد) للترم/الأترام المحددة")
def apply_default_subjects(modeladmin, request, queryset):
    names = getattr(settings, "DEFAULT_SUBJECTS", [])
    if not names:
        messages.error(request, "DEFAULT_SUBJECTS غير معرّفة في settings.")
        return

    # إن وُجد موديل Offering نحاول استخدامه
    Offering = None
    if OFFERING_MODEL_NAME:
        try:
            Offering = apps.get_model("edu", OFFERING_MODEL_NAME)
        except LookupError:
            Offering = None  # نكمل بدونها

    created_total = 0
    for term in queryset:
        for name in names:
            subj, _ = Subject.objects.get_or_create(name=name)
            if Offering:
                _, created = Offering.objects.get_or_create(term=term, subject=subj)
                created_total += int(created)
            else:
                # لو ما عندك Offering: يكفي وجود Subject،
                # والقوائم تبنى بالفلترة (Lesson.objects.filter(term=..., subject=...)).
                pass

    if Offering:
        messages.success(request, f"تم إنشاء/استكمال الربط لمجموع: {created_total} مادة/ترم.")
    else:
        messages.success(request, "تم التأكد من وجود المواد الافتراضية. (لا يوجد موديل ربط Offering).")

@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("id", "year", "number")
    actions = [apply_default_subjects]

# سجّل Subject لو لم يكن مسجلاً
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(SubjectOffering)
class SubjectOfferingAdmin(admin.ModelAdmin):
    list_display = ('id', 'term', 'subject')
    list_filter = ('term__year__number', 'term__number', 'subject__name')
    search_fields = ('subject__name',)

from .models import SubjectSchedule
@admin.register(SubjectSchedule)
class SubjectScheduleAdmin(admin.ModelAdmin):
    list_display = ('offering', 'weekday', 'lecture_no')
    list_filter  = ('weekday', 'offering__term__year__number', 'offering__term__number', 'offering__subject__name')
    search_fields = ('offering__subject__name',)
