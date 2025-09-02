from django.contrib import admin, messages
from django.conf import settings
from django.apps import apps
from .models import (
    Year, Term, Subject, SubjectOffering, Lesson, LessonContent, SubjectSchedule,Week, WeeklyQuiz, WeeklyQuestion
)

# سجّل النماذج الأساسية
admin.site.register(Lesson)
admin.site.register(LessonContent)


# ===== أكشن: إنشاء فصول 1 و2 لكل سنة (Idempotent) =====
@admin.action(description="إنشاء فصول (1 و2) للسنة/السنين المحددة (لن يكرر الموجود)")
def ensure_terms_action(modeladmin, request, queryset):
    created = 0
    for y in queryset:
        for n in (1, 2):
            _, c = Term.objects.get_or_create(year=y, number=n)
            created += int(c)
    messages.success(request, f"تم إنشاء {created} فصل جديد (إن وُجد ناقص).")

@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    list_display = ('id', 'number')
    list_filter = ('number',)
    actions = [ensure_terms_action]
    def save_model(self, request, obj, form, change):
        if not getattr(obj, 'owner_id', None):
            obj.owner = request.user
        return super().save_model(request, obj, form, change)

# ===== أكشن: إنشاء مواد افتراضية (SubjectOffering) للترم =====
OFFERING_MODEL_NAME = "SubjectOffering"  # لدينا موديل الربط فعلاً

@admin.action(description="تطبيق المناهج الافتراضية (7 مواد) للترم/الأترام المحددة")
def apply_default_subjects(modeladmin, request, queryset):
    names = getattr(settings, "DEFAULT_SUBJECTS", [])
    if not names:
        messages.error(request, "DEFAULT_SUBJECTS غير معرّفة في settings.")
        return

    Offering = None
    try:
        Offering = apps.get_model("edu", OFFERING_MODEL_NAME)
    except LookupError:
        Offering = None

    created_total = 0
    for term in queryset:
        owner = getattr(term.year, 'owner', None)
        for name in names:
            if owner:
                subj, _ = Subject.objects.get_or_create(owner=owner, name=name)
            else:
                subj, _ = Subject.objects.get_or_create(name=name)
            if Offering:
                _, created = Offering.objects.get_or_create(term=term, subject=subj)
                created_total += int(created)

    if Offering:
        messages.success(request, f"تم إنشاء/استكمال الربط لمجموع: {created_total} مادة/ترم.")
    else:
        messages.success(request, "تم التأكد من وجود المواد الافتراضية (لا يوجد موديل ربط).")

@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("id", "year", "number")
    list_filter = ("year__number", "number")
    actions = [apply_default_subjects]

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    def save_model(self, request, obj, form, change):
        if not getattr(obj, 'owner_id', None):
            obj.owner = request.user
        return super().save_model(request, obj, form, change)

@admin.register(SubjectOffering)
class SubjectOfferingAdmin(admin.ModelAdmin):
    list_display = ('id', 'term', 'subject')
    list_filter = ('term__year__number', 'term__number', 'subject__name')
    search_fields = ('subject__name',)

@admin.register(SubjectSchedule)
class SubjectScheduleAdmin(admin.ModelAdmin):
    list_display = ('offering', 'weekday', 'lecture_no')
    list_filter  = ('weekday', 'offering__term__year__number', 'offering__term__number', 'offering__subject__name')
    search_fields = ('offering__subject__name',)



@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ('term', 'number')
    list_filter = ('term',)

class WeeklyQuestionInline(admin.TabularInline):
    model = WeeklyQuestion
    extra = 0

@admin.register(WeeklyQuiz)
class WeeklyQuizAdmin(admin.ModelAdmin):
    list_display = ('offering', 'week', 'title', 'is_published')
    list_filter = ('offering__term', 'offering__subject', 'week__number', 'is_published')
    inlines = [WeeklyQuestionInline]
