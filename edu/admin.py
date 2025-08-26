from django.contrib import admin
from .models import Year, Term, Subject, SubjectOffering, Lesson, LessonContent, Question


admin.site.register(Lesson)
admin.site.register(LessonContent)
admin.site.register(Question)

@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    list_display = ('id', 'number')
    list_filter = ('number',)

@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('id', 'year', 'number')
    list_filter = ('year__number', 'number')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

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
