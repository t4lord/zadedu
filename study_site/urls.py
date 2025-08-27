# study_site/urls.py
from django.contrib import admin
from django.urls import path
from edu.views import (
    home_view, select_term_view, set_term_view, change_term_view, term_subjects_view,
    lessons_list_view, lesson_create_view, lesson_update_view, lesson_delete_view, lesson_manage_view,
    lesson_detail_view, lesson_questions_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
<<<<<<< HEAD
=======
    path('healthz', views.healthz, name='healthz'),
>>>>>>> ea62e24 (feat: <وصف التعديل>)
    path('', select_term_view, name='home'),
    path('', home_view, name='home'),
    path('select-term/', select_term_view, name='select_term'),
    path('set-term/', set_term_view, name='set_term'),
    path('change-term/', change_term_view, name='change_term'),

    path('term/<int:term_id>/subjects/', term_subjects_view, name='term_subjects'),

    # دروس المادة داخل الفصل (CRUD)
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/', lessons_list_view, name='lessons_list'),
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/create/', lesson_create_view, name='lesson_create'),
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/edit/', lesson_update_view, name='lesson_update'),
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/delete/', lesson_delete_view, name='lesson_delete'),

    # إدارة الدرس (تحرير)
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/', lesson_manage_view, name='lesson_manage'),

    # العرض الحقيقي (قراءة فقط)
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/view/', lesson_detail_view, name='lesson_detail'),
    path('term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/questions/', lesson_questions_view, name='lesson_questions'),
    
]
