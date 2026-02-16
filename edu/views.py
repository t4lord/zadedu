# edu/views.py
from django.apps import apps
from django.db import connection
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.db.models import Prefetch, Count, Exists, OuterRef, Q
from django.forms import ModelForm
from django.conf import settings
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .models import Year, Term, SubjectOffering, Lesson, LessonContent, SubjectSchedule,Week, WeeklyQuiz, WeeklyQuestion,WeeklyChoice,QuestionType
from django.db import transaction
from datetime import date


def healthz(request):
    return HttpResponse("ok")

# مفاتيح الجلسة/الكوكي
SESSION_KEY = 'selected_term_id'
COOKIE_KEY = "active_term_id"
COOKIE_MAX_AGE = 60 * 60 * 24 * 180  # 180 يوم

# ===================== اختيار السنة والفصل (جديد) =====================

def select_year_term_view(request):
    # العلاقة العكسية الصحيحة هي "terms" (من فحص /diag-models/)
    rel_name = "terms"
    years_qs = Year.objects.filter(owner=request.user).order_by("id").prefetch_related(
        Prefetch(rel_name, queryset=Term.objects.order_by("number"))
    )

    year_groups = []
    for y in years_qs:
        terms_manager = getattr(y, rel_name)  # y.terms
        year_groups.append({"year": y, "terms": list(terms_manager.all())})

    # لو كان عندك فصل محفوظ، وجِّه مباشرة لواجهة المناهج
    active_id = request.session.get(COOKIE_KEY) or request.COOKIES.get(COOKIE_KEY)
    active_term = Term.objects.select_related("year").filter(pk=active_id, year__owner=request.user).first()

    # ملاحظة: عند الرغبة في إيقاف التوجيه المؤتمت مؤقتًا لأجل الاختيار من جديد،
    # يمكنك فتح الصفحة مع ?stay=1
    if active_term and request.GET.get("stay") != "1":
        return redirect("subjects_grid", term_id=active_term.id)

    return render(request, "select_year_term.html", {
        "year_groups": year_groups,
        "active_term": active_term,
    })

@require_POST
def set_active_term_view(request):
    term_id = request.POST.get("term_id")
    term = get_object_or_404(Term, pk=term_id, year__owner=request.user)

    request.session[COOKIE_KEY] = str(term.id)
    # نحو صفحة المناهج
    resp = redirect("subjects_grid", term_id=term.id)
    resp.set_cookie(
        COOKIE_KEY, str(term.id),
        max_age=COOKIE_MAX_AGE,
        secure=not settings.DEBUG,
        samesite="Lax",
        httponly=False,
    )
    messages.info(request, f"تم اختيار الفصل: سنة {term.year.number} — فصل {term.number}.")
    return resp

def clear_active_term_view(request):
    resp = redirect("select_year_term")
    request.session.pop(COOKIE_KEY, None)
    resp.delete_cookie(COOKIE_KEY)
    return resp

# ===================== تشخيص بسيط =====================

def diag_db(request):
    cfg = connection.settings_dict.copy()
    cfg.pop("PASSWORD", None)
    cfg.pop("OPTIONS", None)
    return JsonResponse({
        "engine": cfg.get("ENGINE"),
        "name": cfg.get("NAME"),
        "host": cfg.get("HOST"),
        "port": cfg.get("PORT"),
        "user": cfg.get("USER"),
    })

def diag_models(request):
    data = {}
    for model in apps.get_app_config('edu').get_models():
        fields = []
        for f in model._meta.get_fields():
            fields.append({"name": f.name, "type": f.__class__.__name__})
        data[model.__name__.lower()] = fields
    return JsonResponse(data)

def diag_year_term(request):
    rel_name = "terms"
    out = []
    for y in Year.objects.filter(owner=request.user).order_by("id"):
        terms = list(getattr(y, rel_name).all().order_by("number").values("id", "number"))
        out.append({"year_id": y.id, "year_number": y.number, "terms": terms})
    active = request.session.get(COOKIE_KEY) or request.COOKIES.get(COOKIE_KEY)
    return JsonResponse({"active_term_id": active, "years": out})

# ===================== التسجيل (حساب جديد) =====================
def register_view(request):
    if request.user.is_authenticated:
        return redirect('select_year_term')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # تهيئة بيانات المستخدم: سنوات 1..2 + فصول 1..2 + مواد افتراضية وربطها بالفصول
            try:
                y1 = Year.objects.create(owner=user, number=1)
                y2 = Year.objects.create(owner=user, number=2)
                for y in (y1, y2):
                    for n in (1, 2):
                        term = Term.objects.create(year=y, number=n)
                        # مواد افتراضية بحسب الإعدادات
                        for name in getattr(settings, 'DEFAULT_SUBJECTS', []):
                            subj, _ = Subject.objects.get_or_create(owner=user, name=name)
                            SubjectOffering.objects.get_or_create(term=term, subject=subj)
                        # أسابيع افتراضية
                        ensure_weeks_for_term(term)
            except Exception:
                pass
            auth_login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/'
            return redirect(next_url)
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', { 'form': form, 'next': request.GET.get('next','') })

# ===================== واجهات قديمة (اختياري إبقاؤها) =====================

def home_view(request):
    term_id = request.session.get(SESSION_KEY)
    if term_id:
        return redirect('term_subjects', term_id=term_id)
    return redirect('select_term')

def select_term_view(request):
    years = Year.objects.filter(owner=request.user).order_by('number').prefetch_related('terms')
    return render(request, 'select_term.html', {'years': years})

def set_term_view(request):
    if request.method != 'POST':
        return redirect('select_term')
    try:
        year_num = int(request.POST.get('year', 0))
        term_num = int(request.POST.get('term', 0))
    except (TypeError, ValueError):
        return redirect('select_term')
    term = Term.objects.filter(year__owner=request.user, year__number=year_num, number=term_num).first()
    if not term:
        return redirect('select_term')
    request.session[SESSION_KEY] = term.id
    messages.info(request, f"تم اختيار الفصل: سنة {term.year.number} — فصل {term.number}.")
    return redirect('term_subjects', term_id=term.id)

def change_term_view(request):
    if SESSION_KEY in request.session:
        del request.session[SESSION_KEY]
        request.session.modified = True
    return redirect('select_term')

# ===================== صفحة مناهج الفصل =====================

from django.db.models import Min, Exists, OuterRef, Count, Q
from collections import defaultdict
AR_DAYS = ['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']


def term_subjects_view(request, term_id: int):
    term = get_object_or_404(Term, id=term_id, year__owner=request.user)

    # اليوم الحالي + معاينة ?preview_day=0..6
    weekday = timezone.localdate().weekday()
    pd = request.GET.get('preview_day')
    if pd is not None and pd.isdigit():
        w = int(pd)
        if 0 <= w <= 6:
            weekday = w

    # اكتشاف ما إذا كانت الأيام مخزنة 0..6 أو 1..7
    base = SubjectSchedule.objects.filter(offering__term=term).aggregate(m=Min('weekday'))['m']
    base_is_one = (base == 1)
    weekday_db = weekday + 1 if base_is_one else weekday

    schedules_today = SubjectSchedule.objects.filter(
        offering=OuterRef('pk'),
        weekday=weekday_db
    )

    # أسبوع التقدّم (?week=1..WEEKS_PER_TERM)
    try:
        progress_week = int(request.GET.get('week', '1'))
    except ValueError:
        progress_week = 1
    progress_week = max(1, min(WEEKS_PER_TERM, progress_week))

    offerings_qs = (
        SubjectOffering.objects
        .filter(term=term)
        .select_related('subject')
        .annotate(
            lesson_count=Count('lessons', distinct=True),
            completed_count=Count('lessons', filter=Q(lessons__content__body__isnull=False) & ~Q(lessons__content__body=''), distinct=True),
            expected_sessions=Count('schedules__weekday', distinct=True),
            weekly_done_count=Count('weekly_quizzes__questions', filter=Q(weekly_quizzes__week__number=progress_week), distinct=True),
            is_today=Exists(schedules_today),
        )
        .order_by('subject__name')
        .distinct()
    )

    # ❌ لا تستخدم prefetch_related('subjectschedule_set') لأنه غير معروف
    # ✅ كوّن خريطة أيام الجدولة ثم علّقها على الكائنات
    rows = SubjectSchedule.objects.filter(offering__term=term).values_list('offering_id', 'weekday')
    sched_map = defaultdict(list)
    for off_id, wd in rows:
        sched_map[off_id].append(wd)

    offerings = list(offerings_qs)
    for o in offerings:
        o.sched_days = sched_map.get(o.id, [])  # خاصية آمنة للاستخدام بالقالب
        if not getattr(o, 'expected_sessions', 0):
            o.expected_sessions = 1 if (getattr(o, 'subject', None) and o.subject.name == 'الفقه') else 2

    return render(request, 'term_subjects.html', {
        'term': term,
        'offerings': offerings,
        'weekday_name': AR_DAYS[weekday],
        'weekday_index': weekday,
        'weekday_db': weekday_db,
        'base_is_one': base_is_one,
        'has_any_schedule': bool(rows),
        'AR_DAYS': AR_DAYS,
        'progress_week': progress_week,
        'debug': request.GET.get('debug') in {'1','true','yes','on'},
    })

from collections import defaultdict
from django.db.models import Min, Exists, OuterRef, Count
# alias بسيط لتجنّب كسر الروابط
# alias بسيط لتجنّب كسر الروابط
def subjects_grid_view(request, term_id): 
    from django.db.models import Min, Exists, OuterRef, Count, Q

    term = get_object_or_404(Term, id=term_id, year__owner=request.user)

    # اليوم الحالي بالتوقيت المحلي
    weekday = timezone.localdate().weekday()  # Mon=0 .. Sun=6

    # اكتشاف 0..6 أو 1..7 (سلامة فقط)
    base = SubjectSchedule.objects.filter(offering__term=term).aggregate(m=Min('weekday'))['m']
    base_is_one = (base == 1)
    weekday_db = weekday + 1 if base_is_one else weekday

    # هل اليوم مجدول لهذه المادة؟
    schedules_today = SubjectSchedule.objects.filter(
        offering=OuterRef('pk'),
        weekday=weekday_db
    )

    # أسبوع التقدّم (?week=1..WEEKS_PER_TERM)
    try:
        progress_week = int(request.GET.get('week', '1'))
    except ValueError:
        progress_week = 1
    progress_week = max(1, min(WEEKS_PER_TERM, progress_week))

    # اجلب العروض مع subject وعدد الدروس و is_today + **prefetch schedules**
    # ✅ إضافة weekly_questions_count لعرض عدد الأسئلة الأسبوعية في القالب
    offerings = list(
        SubjectOffering.objects
        .filter(term=term)
        .select_related('subject')
        .prefetch_related('schedules')  # لكي تستفيد sched_days من الكاش وتتجنب N+1
        .annotate(
            lesson_count=Count('lessons', distinct=True),
            completed_count=Count('lessons', filter=Q(lessons__content__body__isnull=False) & ~Q(lessons__content__body=''), distinct=True),
            expected_sessions=Count('schedules__weekday', distinct=True),
            weekly_done_count=Count('weekly_quizzes__questions', filter=Q(weekly_quizzes__week__number=progress_week), distinct=True),
            is_today=Exists(schedules_today),
            weekly_questions_count=Count('weekly_quizzes__questions', distinct=True),  # ← هذا السطر الجديد
        )
        .order_by('subject__name')
        .distinct()
    )

    has_any_schedule = SubjectSchedule.objects.filter(offering__term=term).exists()

    # ضبط القيمة الافتراضية المتوقعة للجلسات الأسبوعية عند عدم وجود جدول: 2، عدا الفقه 1
    for o in offerings:
        if not getattr(o, 'expected_sessions', 0):
            o.expected_sessions = 1 if (getattr(o, 'subject', None) and o.subject.name == 'الفقه') else 2

    return render(request, 'term_subjects.html', {
        'term': term,
        'offerings': offerings,
        'weekday_name': AR_DAYS[weekday],
        'weekday_index': weekday,
        'weekday_db': weekday_db,
        'base_is_one': base_is_one,
        'has_any_schedule': has_any_schedule,
        'AR_DAYS': AR_DAYS,
        'progress_week': progress_week,
        'debug': request.GET.get('debug') in {'1','true','yes','on'},
    })

# ===================== Forms =====================

class LessonForm(ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'order']
        labels = {'title': 'عنوان الدرس', 'order': 'الترتيب'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'inp'}),
            'order': forms.NumberInput(attrs={'class': 'inp', 'min': 1}),
        }

class LessonContentForm(ModelForm):
    class Meta:
        model = LessonContent
        fields = ['body']
        labels = {'body': 'المحتوى النصّي'}
        widgets = {'body': forms.Textarea(attrs={'class': 'inp', 'rows': 8})}

# ===================== Helpers =====================

def get_offering_or_404(request, term_id, subject_id):
    return get_object_or_404(SubjectOffering, term_id=term_id, subject_id=subject_id, term__year__owner=request.user)

# ===================== قائمة الدروس + CRUD =====================

def lessons_list_view(request, term_id, subject_id):
    offering = get_offering_or_404(request, term_id, subject_id)
    lessons = (
        offering.lessons
        .select_related('content')  # لتحسين الاستعلام عند عرض توفر المحتوى
        .order_by('order', 'id')
    )
    return render(request, 'lessons_list.html', {
        'offering': offering,
        'term': offering.term,
        'subject': offering.subject,
        'lessons': lessons,
    })

def lesson_create_view(request, term_id, subject_id):
    offering = get_offering_or_404(request, term_id, subject_id)
    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.offering = offering
            lesson.save()
            LessonContent.objects.get_or_create(lesson=lesson)
            messages.success(request, 'تم إنشاء الدرس بنجاح.')
            return redirect('lessons_list', term_id=term_id, subject_id=subject_id)
    else:
        form = LessonForm()
    return render(request, 'lesson_form.html', {'offering': offering, 'form': form, 'mode': 'create'})

def lesson_update_view(request, term_id, subject_id, lesson_id):
    offering = get_offering_or_404(request, term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات الدرس بنجاح.')
            return redirect('lessons_list', term_id=term_id, subject_id=subject_id)
    else:
        form = LessonForm(instance=lesson)
    return render(request, 'lesson_form.html', {'offering': offering, 'form': form, 'mode': 'update', 'lesson': lesson})

def lesson_delete_view(request, term_id, subject_id, lesson_id):
    offering = get_offering_or_404(request, term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, 'تم حذف الدرس.')
        return redirect('lessons_list', term_id=term_id, subject_id=subject_id)
    return render(request, 'lesson_confirm_delete.html', {'offering': offering, 'lesson': lesson})

# ===================== إدارة الدرس (تحرير محتوى فقط) =====================

def lesson_manage_view(request, term_id, subject_id, lesson_id):
    """
    إدارة محتوى الدرس فقط (تمت إزالة إدارة أسئلة الدرس ضمن التنظيف تمهيدًا للنظام الأسبوعي).
    """
    offering = get_offering_or_404(request, term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    content, _ = LessonContent.objects.get_or_create(lesson=lesson)

    # تحديث المحتوى
    if request.method == 'POST' and request.POST.get('form_name') == 'content':
        cform = LessonContentForm(request.POST, instance=content)
        if cform.is_valid():
            cform.save()
            messages.success(request, 'تم حفظ محتوى الدرس.')
            return redirect('lesson_manage', term_id=term_id, subject_id=subject_id, lesson_id=lesson_id)
    else:
        cform = LessonContentForm(instance=content)

    return render(request, 'lesson_manage.html', {
        'offering': offering,
        'term': offering.term,
        'subject': offering.subject,
        'lesson': lesson,
        'cform': cform,
    })

# ===================== العرض الحقيقي (قراءة فقط) =====================

def lesson_detail_view(request, term_id, subject_id, lesson_id):
    """يعرض محتوى الدرس ويحفظه."""
    offering = get_offering_or_404(request, term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    content, _ = LessonContent.objects.get_or_create(lesson=lesson)

    if request.method == 'POST' and request.POST.get('form_name') == 'save_content':
        body_html = request.POST.get('body_html', '').strip()
        content.body = body_html
        content.save()
        messages.success(request, 'تم حفظ المحتوى.')
        return redirect('lesson_detail', term_id=term_id, subject_id=subject_id, lesson_id=lesson_id)

    return render(request, 'lesson_detail.html', {
        'offering': offering,
        'term': offering.term,
        'subject': offering.subject,
        'lesson': lesson,
        'content': content,
    })


WEEKS_PER_TERM = 12  # عدّلها لو تبغى عددًا آخر

def ensure_weeks_for_term(term):
    existing = set(term.weeks.values_list('number', flat=True))
    to_create = [Week(term=term, number=n) for n in range(1, WEEKS_PER_TERM + 1) if n not in existing]
    if to_create:
        Week.objects.bulk_create(to_create)

class WeeklyQuestionForm(forms.ModelForm):
    class Meta:
        model = WeeklyQuestion
        fields = ['text', 'qtype', 'correct_bool', 'order']
        labels = {'text':'نص السؤال','qtype':'النوع','correct_bool':'الإجابة الصحيحة (لصح/خطأ)','order':'الترتيب'}
        widgets = {
            'text': forms.Textarea(attrs={'class':'inp','rows':3}),
            'qtype': forms.Select(attrs={'class':'inp'}),
            'correct_bool': forms.Select(choices=[('', '— اختر —'), (True, 'صح'), (False, 'خطأ')], attrs={'class':'inp'}),
            'order': forms.NumberInput(attrs={'class':'inp','min':0}),
        }

class WeeklyChoiceForm(forms.ModelForm):
    class Meta:
        model = WeeklyChoice
        fields = ['text', 'is_correct', 'order']
        labels = {'text':'نص الخيار','is_correct':'صحيح؟','order':'ترتيب'}
        widgets = {
            'text': forms.TextInput(attrs={'class':'inp'}),
            'is_correct': forms.CheckboxInput(attrs={}),
            'order': forms.NumberInput(attrs={'class':'inp','min':0}),
        }

@transaction.atomic
def weekly_quiz_manage_view(request, term_id, subject_id):
    offering = get_offering_or_404(request, term_id, subject_id)
    term = offering.term

    ensure_weeks_for_term(term)

    try:
        week_number = int(request.GET.get('week', '1'))
    except ValueError:
        week_number = 1
    week_number = max(1, min(WEEKS_PER_TERM, week_number))

    week = Week.objects.filter(term=term, number=week_number).first() or Week.objects.create(term=term, number=week_number)

    quiz, _ = WeeklyQuiz.objects.get_or_create(
        offering=offering, week=week, defaults={'title': f"أسئلة أسبوع {week_number}"}
    )

    # ============ إضافة سؤال ============
    if request.method == 'POST' and request.POST.get('form_name') == 'add_question':
        qform = WeeklyQuestionForm(request.POST)
        if qform.is_valid():
            q = qform.save(commit=False)
            q.quiz = quiz
            
            # معالجة correct_bool + خيارات MCQ مباشرة في نفس الطلب لتجنب إعادة التحميل البطيء
            if q.qtype == QuestionType.MCQ:
                q.correct_bool = None
                q.correct_text = None
            elif q.qtype == QuestionType.TF:
                cb_raw = request.POST.get('correct_bool', '').strip().lower()
                if cb_raw == 'on':
                    q.correct_bool = True
                    q.correct_text = None
                elif cb_raw == 'off':
                    q.correct_bool = False
                    # احفظ النص إذا وُجد (حقل اختياري)
                    q.correct_text = request.POST.get('correct_text', '').strip() or None
                else:
                    qform.add_error('correct_bool', 'اختر صح أو خطأ.')
            
            if not qform.errors:
                q.save()

                # إنشاء خيارات MCQ فورًا بدل التخزين المؤقت في المتصفح
                if q.qtype == QuestionType.MCQ:
                    choices = []
                    correct_idx = request.POST.get('mcq_correct', '').strip()
                    for idx, field in enumerate(['mcq_choice1', 'mcq_choice2', 'mcq_choice3'], start=1):
                        txt = (request.POST.get(field) or '').strip()
                        if not txt:
                            continue
                        choices.append(WeeklyChoice(
                            question=q,
                            text=txt,
                            is_correct=(str(idx) == correct_idx),
                            order=idx,
                        ))

                    if len(choices) < 2 or not any(c.is_correct for c in choices):
                        # تراجع عن إنشاء السؤال إن لم تكن البيانات مكتملة
                        q.delete()
                        qform.add_error(None, 'للاختيارات: أدخل خيارين على الأقل وحدّد الإجابة الصحيحة.')
                    else:
                        WeeklyChoice.objects.bulk_create(choices)
                
            if not qform.errors:
                messages.success(request, 'تم إضافة السؤال.')
                return redirect(f"{request.path}?week={week_number}")
    else:
        qform = WeeklyQuestionForm()

    # ============ تعديل سؤال ============
    if request.method == 'POST' and request.POST.get('form_name', '').startswith('edit_question_'):
        qid = request.POST.get('question_id')
        qobj = get_object_or_404(WeeklyQuestion, id=qid, quiz=quiz)
        qedit = WeeklyQuestionForm(request.POST, instance=qobj)
        if qedit.is_valid():
            q = qedit.save(commit=False)
            
            # معالجة correct_bool: تحويل on/off إلى True/False  
            if q.qtype == QuestionType.MCQ:
                q.correct_bool = None
                q.correct_text = None
            elif q.qtype == QuestionType.TF:
                cb_raw = request.POST.get('correct_bool', '').strip().lower()
                if cb_raw == 'on':
                    q.correct_bool = True
                    q.correct_text = None
                elif cb_raw == 'off':
                    q.correct_bool = False
                    q.correct_text = request.POST.get('correct_text', '').strip() or None
                else:
                    q.correct_bool = None
            
            if not qedit.errors:
                q.save()
                messages.success(request, 'تم تعديل السؤال.')
                return redirect(f"{request.path}?week={week_number}")

    # ============ حذف سؤال ============
    if request.method == 'POST' and request.POST.get('form_name') == 'delete_question':
        qid = request.POST.get('question_id')
        qobj = get_object_or_404(WeeklyQuestion, id=qid, quiz=quiz)
        qobj.delete()
        messages.success(request, 'تم حذف السؤال.')
        return redirect(f"{request.path}?week={week_number}")

    # ============ خيارات MCQ: إضافة/تعديل/حذف/تعيين صحيح ============
    if request.method == 'POST' and request.POST.get('form_name') == 'add_option':
        qid = request.POST.get('question_id')
        qobj = get_object_or_404(WeeklyQuestion, id=qid, quiz=quiz, qtype=QuestionType.MCQ)
        oform = WeeklyChoiceForm(request.POST)
        if oform.is_valid():
            opt = oform.save(commit=False)
            opt.question = qobj
            opt.save()
            # لو تم وضع is_correct=True لهذا الخيار، ألغِ الصح عن بقية الخيارات
            if opt.is_correct:
                WeeklyChoice.objects.filter(question=qobj).exclude(id=opt.id).update(is_correct=False)
            messages.success(request, 'تم إضافة الخيار.')
            return redirect(f"{request.path}?week={week_number}")

    if request.method == 'POST' and request.POST.get('form_name') == 'edit_option':
        oid = request.POST.get('option_id')
        opt = get_object_or_404(WeeklyChoice, id=oid, question__quiz=quiz, question__qtype=QuestionType.MCQ)
        oform = WeeklyChoiceForm(request.POST, instance=opt)
        if oform.is_valid():
            opt = oform.save()
            if opt.is_correct:
                WeeklyChoice.objects.filter(question=opt.question).exclude(id=opt.id).update(is_correct=False)
            messages.success(request, 'تم حفظ التعديلات على الخيار.')
            return redirect(f"{request.path}?week={week_number}")

    if request.method == 'POST' and request.POST.get('form_name') == 'delete_option':
        oid = request.POST.get('option_id')
        opt = get_object_or_404(WeeklyChoice, id=oid, question__quiz=quiz, question__qtype=QuestionType.MCQ)
        opt.delete()
        messages.success(request, 'تم حذف الخيار.')
        return redirect(f"{request.path}?week={week_number}")

    # ============ بيانات العرض ============
    # جلب الأسئلة بدون التكرار
    questions = quiz.questions.order_by('order', 'id')
    
    # تحميل الخيارات بشكل منفصل لتجنب التكرار
    questions_dict = {}
    for q in questions:
        questions_dict[q.id] = q
        q.choices_list = list(q.choices.order_by('order', 'id'))
    
    questions = list(questions_dict.values())
    weeks = list(term.weeks.order_by('number'))

    return render(request, 'weekly_quiz_manage.html', {
        'term': term,
        'subject': offering.subject,
        'offering': offering,
        'quiz': quiz,
        'week': week,
        'weeks': weeks,
        'qform': qform,
        'questions': questions,
        'QuestionType': QuestionType,
        'WEEKS_PER_TERM': WEEKS_PER_TERM,
    })

def exam_take_view(request, term_id: int, subject_id: int, scope: str):
    offering = get_offering_or_404(request, term_id, subject_id)
    term = offering.term
    subject = offering.subject  # اختياري لو تحتاجه للعرض فقط

    scope = (scope or '').lower()
    if scope == 'm1':
        start_w, end_w = 1, 4
        scope_label = "اختبار الشهر الأول (1–4)"
    elif scope == 'm2':
        start_w, end_w = 5, 8
        scope_label = "اختبار الشهر الثاني (5–8)"
    elif scope == 'final':
        start_w, end_w = 1, 12
        scope_label = "الاختبار النهائي (1–12)"
    else:
        raise Http404("نطاق الاختبار غير معروف")

    # الأسابيع المطلوبة
    weeks = Week.objects.filter(term=term, number__gte=start_w, number__lte=end_w).order_by('number')
    week_numbers = list(weeks.values_list('number', flat=True))

    # ✅ التصحيح هنا: التصفية عبر quiz__offering و quiz__week__
    questions = (
        WeeklyQuestion.objects
        .filter(
            quiz__offering=offering,
            quiz__week__number__in=week_numbers,
        )
        .select_related('quiz', 'quiz__week')
        .prefetch_related(Prefetch('choices', queryset=WeeklyChoice.objects.order_by('order', 'id')))
        .order_by('quiz__week__number', 'id')
    )

    shuffle = request.GET.get('shuffle') in {'1', 'true', 'yes', 'on'}

    return render(request, 'exam_take.html', {
        'term': term,
        'subject': subject,
        'offering': offering,
        'scope': scope,
        'scope_label': scope_label,
        'week_numbers': week_numbers,
        'questions': questions,
        'shuffle': shuffle,
        'QuestionType': QuestionType,  # ✅ لو القالب يقارن بـ QuestionType.MCQ/TF
    })
