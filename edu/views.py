# edu/views.py
from django.apps import apps
from django.db import connection
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.db.models import Prefetch, Count, Exists, OuterRef
from django.forms import ModelForm
from django.conf import settings
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
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
    years_qs = Year.objects.all().order_by("id").prefetch_related(
        Prefetch(rel_name, queryset=Term.objects.order_by("number"))
    )

    year_groups = []
    for y in years_qs:
        terms_manager = getattr(y, rel_name)  # y.terms
        year_groups.append({"year": y, "terms": list(terms_manager.all())})

    # لو كان عندك فصل محفوظ، وجِّه مباشرة لواجهة المناهج
    active_id = request.session.get(COOKIE_KEY) or request.COOKIES.get(COOKIE_KEY)
    active_term = Term.objects.select_related("year").filter(pk=active_id).first()

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
    term = get_object_or_404(Term, pk=term_id)

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
    for y in Year.objects.all().order_by("id"):
        terms = list(getattr(y, rel_name).all().order_by("number").values("id", "number"))
        out.append({"year_id": y.id, "year_number": y.number, "terms": terms})
    active = request.session.get(COOKIE_KEY) or request.COOKIES.get(COOKIE_KEY)
    return JsonResponse({"active_term_id": active, "years": out})

# ===================== واجهات قديمة (اختياري إبقاؤها) =====================

def home_view(request):
    term_id = request.session.get(SESSION_KEY)
    if term_id:
        return redirect('term_subjects', term_id=term_id)
    return redirect('select_term')

def select_term_view(request):
    years = Year.objects.order_by('number').prefetch_related('terms')
    return render(request, 'select_term.html', {'years': years})

def set_term_view(request):
    if request.method != 'POST':
        return redirect('select_term')
    try:
        year_num = int(request.POST.get('year', 0))
        term_num = int(request.POST.get('term', 0))
    except (TypeError, ValueError):
        return redirect('select_term')
    term = Term.objects.filter(year__number=year_num, number=term_num).first()
    if not term:
        return redirect('select_term')
    request.session[SESSION_KEY] = term.id
    return redirect('term_subjects', term_id=term.id)

def change_term_view(request):
    if SESSION_KEY in request.session:
        del request.session[SESSION_KEY]
        request.session.modified = True
    return redirect('select_term')

# ===================== صفحة مناهج الفصل =====================

from django.db.models import Min, Exists, OuterRef, Count
from collections import defaultdict
AR_DAYS = ['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']


def term_subjects_view(request, term_id: int):
    term = get_object_or_404(Term, id=term_id)

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

    offerings_qs = (
        SubjectOffering.objects
        .filter(term=term)
        .select_related('subject')
        .annotate(
            lesson_count=Count('lessons', distinct=True),
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

    return render(request, 'term_subjects.html', {
        'term': term,
        'offerings': offerings,
        'weekday_name': AR_DAYS[weekday],
        'weekday_index': weekday,
        'weekday_db': weekday_db,
        'base_is_one': base_is_one,
        'has_any_schedule': bool(rows),
        'debug': request.GET.get('debug') in {'1','true','yes','on'},
    })

from collections import defaultdict
from django.db.models import Min, Exists, OuterRef, Count
# alias بسيط لتجنّب كسر الروابط
# alias بسيط لتجنّب كسر الروابط
def subjects_grid_view(request, term_id):
    from django.db.models import Min, Exists, OuterRef, Count

    term = get_object_or_404(Term, id=term_id)

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

    # اجلب العروض مع subject وعدد الدروس و is_today + **prefetch schedules**
    offerings = list(
        SubjectOffering.objects
        .filter(term=term)
        .select_related('subject')
        .prefetch_related('schedules')  # ✅ حتى خاصية sched_days تستخدم الكاش بدون N+1
        .annotate(
            lesson_count=Count('lessons', distinct=True),
            is_today=Exists(schedules_today),
        )
        .order_by('subject__name')
        .distinct()
    )

    has_any_schedule = SubjectSchedule.objects.filter(offering__term=term).exists()

    return render(request, 'term_subjects.html', {
        'term': term,
        'offerings': offerings,
        'weekday_name': AR_DAYS[weekday],
        'weekday_index': weekday,
        'weekday_db': weekday_db,
        'base_is_one': base_is_one,
        'has_any_schedule': has_any_schedule,
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

def get_offering_or_404(term_id, subject_id):
    return get_object_or_404(SubjectOffering, term_id=term_id, subject_id=subject_id)

# ===================== قائمة الدروس + CRUD =====================

def lessons_list_view(request, term_id, subject_id):
    offering = get_offering_or_404(term_id, subject_id)
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
    offering = get_offering_or_404(term_id, subject_id)
    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.offering = offering
            lesson.save()
            LessonContent.objects.get_or_create(lesson=lesson)
            return redirect('lessons_list', term_id=term_id, subject_id=subject_id)
    else:
        form = LessonForm()
    return render(request, 'lesson_form.html', {'offering': offering, 'form': form, 'mode': 'create'})

def lesson_update_view(request, term_id, subject_id, lesson_id):
    offering = get_offering_or_404(term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            return redirect('lessons_list', term_id=term_id, subject_id=subject_id)
    else:
        form = LessonForm(instance=lesson)
    return render(request, 'lesson_form.html', {'offering': offering, 'form': form, 'mode': 'update', 'lesson': lesson})

def lesson_delete_view(request, term_id, subject_id, lesson_id):
    offering = get_offering_or_404(term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    if request.method == 'POST':
        lesson.delete()
        return redirect('lessons_list', term_id=term_id, subject_id=subject_id)
    return render(request, 'lesson_confirm_delete.html', {'offering': offering, 'lesson': lesson})

# ===================== إدارة الدرس (تحرير محتوى فقط) =====================

def lesson_manage_view(request, term_id, subject_id, lesson_id):
    """
    إدارة محتوى الدرس فقط (تمت إزالة إدارة أسئلة الدرس ضمن التنظيف تمهيدًا للنظام الأسبوعي).
    """
    offering = get_offering_or_404(term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    content, _ = LessonContent.objects.get_or_create(lesson=lesson)

    # تحديث المحتوى
    if request.method == 'POST' and request.POST.get('form_name') == 'content':
        cform = LessonContentForm(request.POST, instance=content)
        if cform.is_valid():
            cform.save()
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
    offering = get_offering_or_404(term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    content, _ = LessonContent.objects.get_or_create(lesson=lesson)

    if request.method == 'POST' and request.POST.get('form_name') == 'save_content':
        body_html = request.POST.get('body_html', '').strip()
        content.body = body_html
        content.save()
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
    offering = get_offering_or_404(term_id, subject_id)
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
            # ضمان صحة correct_bool: لا يُستخدم إلا مع TF
            if q.qtype == QuestionType.TF and q.correct_bool is None:
                qform.add_error('correct_bool', 'اختر صح أو خطأ.')
            elif q.qtype == QuestionType.MCQ:
                q.correct_bool = None
            if not qform.errors:
                q.save()
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
            if q.qtype == QuestionType.TF and q.correct_bool is None:
                qedit.add_error('correct_bool', 'اختر صح أو خطأ.')
            elif q.qtype == QuestionType.MCQ:
                q.correct_bool = None
            if not qedit.errors:
                q.save()
                return redirect(f"{request.path}?week={week_number}")

    # ============ حذف سؤال ============
    if request.method == 'POST' and request.POST.get('form_name') == 'delete_question':
        qid = request.POST.get('question_id')
        qobj = get_object_or_404(WeeklyQuestion, id=qid, quiz=quiz)
        qobj.delete()
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
            return redirect(f"{request.path}?week={week_number}")

    if request.method == 'POST' and request.POST.get('form_name') == 'edit_option':
        oid = request.POST.get('option_id')
        opt = get_object_or_404(WeeklyChoice, id=oid, question__quiz=quiz, question__qtype=QuestionType.MCQ)
        oform = WeeklyChoiceForm(request.POST, instance=opt)
        if oform.is_valid():
            opt = oform.save()
            if opt.is_correct:
                WeeklyChoice.objects.filter(question=opt.question).exclude(id=opt.id).update(is_correct=False)
            return redirect(f"{request.path}?week={week_number}")

    if request.method == 'POST' and request.POST.get('form_name') == 'delete_option':
        oid = request.POST.get('option_id')
        opt = get_object_or_404(WeeklyChoice, id=oid, question__quiz=quiz, question__qtype=QuestionType.MCQ)
        opt.delete()
        return redirect(f"{request.path}?week={week_number}")

    # ============ بيانات العرض ============
    questions = (
        quiz.questions
        .prefetch_related('choices')
        .order_by('order', 'id')
    )
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

from django.db.models import Prefetch

def exam_take_view(request, term_id: int, subject_id: int, scope: str):
    offering = get_offering_or_404(term_id, subject_id)
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