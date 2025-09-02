from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from edu import views as V

# لو subjects_grid_view غير معرّف، نستخدم term_subjects_view كبديل آمن
SUBJECTS_GRID = getattr(V, "subjects_grid_view", V.term_subjects_view)

urlpatterns = [
    path("admin/", admin.site.urls),

    # حسابات: تسجيل الدخول/الخروج
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),

    # صحّة
    path("healthz", V.healthz, name="healthz"),

    # اختيار السنة والفصل (النظام الجديد)
    path("", V.select_year_term_view, name="select_year_term"),
    path("set-term/", V.set_active_term_view, name="set_active_term"),
    path("change-term/", V.clear_active_term_view, name="clear_active_term"),

    # صفحة مناهج الفصل (grid)
    path("term/<int:term_id>/", SUBJECTS_GRID, name="subjects_grid"),
    path("term/<int:term_id>/subjects/", V.term_subjects_view, name="term_subjects"),

    # نظام الاختيار القديم (إبقائه متاحًا لمن يحتاجه)
    path("select-term/", V.select_term_view, name="select_term"),
    path("set-term-legacy/", V.set_term_view, name="set_term"),
    path("change-term-legacy/", V.change_term_view, name="change_term"),

    # دروس المادة داخل الفصل (CRUD)
    path("term/<int:term_id>/subject/<int:subject_id>/lessons/", V.lessons_list_view, name="lessons_list"),
    path("term/<int:term_id>/subject/<int:subject_id>/lessons/create/", V.lesson_create_view, name="lesson_create"),
    path("term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/edit/", V.lesson_update_view, name="lesson_update"),
    path("term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/delete/", V.lesson_delete_view, name="lesson_delete"),

    # إدارة الدرس (تحرير المحتوى + الأسئلة)
    path("term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/", V.lesson_manage_view, name="lesson_manage"),

    # العرض الحقيقي + الأسئلة
    path("term/<int:term_id>/subject/<int:subject_id>/lessons/<int:lesson_id>/view/", V.lesson_detail_view, name="lesson_detail"),
    # تشخيص
    path("diag-db/", V.diag_db),
    path("diag-models/", V.diag_models),
    path("diag-year-term/", V.diag_year_term),
    path("term/<int:term_id>/subject/<int:subject_id>/weekly/",V.weekly_quiz_manage_view, name="weekly_quiz_manage"),
    path('term/<int:term_id>/subject/<int:subject_id>/exam/<str:scope>/',V.exam_take_view,name='exam_take'),
]
