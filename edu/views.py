# edu/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.forms import ModelForm
from django.conf import settings
from django.views.decorators.http import require_POST
from .models import Year, Term, SubjectOffering,Lesson, LessonContent, Question, SECTION_CHOICES


from django.http import HttpResponse
def healthz(request): return HttpResponse("ok")

SESSION_KEY = 'selected_term_id'
COOKIE_KEY = "active_term_id"
COOKIE_MAX_AGE = 60 * 60 * 24 * 180  # 180 يوم

def select_year_term_view(request):
    years = Year.objects.all().order_by("id")
    active_id = request.session.get(COOKIE_KEY) or request.COOKIES.get(COOKIE_KEY)
    active_term = Term.objects.filter(pk=active_id).select_related("year").first()
    return render(request, "select_year_term.html", {
        "years": years,
        "active_term": active_term,
    })

@require_POST
def set_active_term_view(request):
    term_id = request.POST.get("term_id")
    term = get_object_or_404(Term, pk=term_id)
    # خزّن الاختيار
    request.session[COOKIE_KEY] = str(term.id)
    resp = redirect("subjects_grid", term_id=term.id)  # غيّر الاسم لو مسارك مختلف
    resp.set_cookie(
        COOKIE_KEY, str(term.id),
        max_age=COOKIE_MAX_AGE,
        secure=not settings.DEBUG,
        samesite="Lax",
        httponly=False,
    )
    return resp
# ===================== جلسة الفصل =====================
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


from django.db.models import Count  # ← أضِف هذا الاستيراد
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone
from .models import SubjectSchedule  # جديد

AR_DAYS = ['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']

def term_subjects_view(request, term_id: int):
    term = get_object_or_404(Term, id=term_id)

    # اليوم الحالي (بتوقيت مشروعك)
    today = timezone.localtime()
    weekday = today.weekday()  # الاثنين=0 .. الأحد=6

    # (للمعاينة اليدوية من المتصفح: ?preview_day=0..6)
    pd = request.GET.get('preview_day')
    if pd is not None and pd.isdigit():
        w = int(pd)
        if 0 <= w <= 6:
            weekday = w

    # فلتر "هل لهذه المادة جدول اليوم؟"
    schedules_today = SubjectSchedule.objects.filter(offering=OuterRef('pk'), weekday=weekday)

    offerings = (
        SubjectOffering.objects
        .filter(term=term)
        .select_related('subject')
        .annotate(
            lesson_count=Count('lessons', distinct=True),  # عدّ صحيح
            is_today=Exists(schedules_today),              # بوليان اليوم
        )
        .order_by('subject__name')
        .distinct()  # منع أي تكرار بسبب الانضمامات
    )

    # احفظ الفصل المختار في الجلسة
    if request.session.get(SESSION_KEY) != term.id:
        request.session[SESSION_KEY] = term.id
        request.session.modified = True

    return render(request, 'term_subjects.html', {
        'term': term,
        'offerings': offerings,
        'weekday_name': AR_DAYS[weekday],
        'weekday_index': weekday,
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


class QuestionForm(ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'section', 'choice1', 'choice2', 'choice3', 'correct']
        labels = {
            'text': 'نص السؤال',
            'section': 'القسم',
            'choice1': 'الخيار 1',
            'choice2': 'الخيار 2',
            'choice3': 'الخيار 3',
            'correct': 'الإجابة الصحيحة',
        }
        widgets = {
            'text': forms.Textarea(attrs={'class': 'inp', 'rows': 3}),
            'section': forms.Select(attrs={'class': 'inp'}),
            'choice1': forms.TextInput(attrs={'class': 'inp'}),
            'choice2': forms.TextInput(attrs={'class': 'inp'}),
            'choice3': forms.TextInput(attrs={'class': 'inp'}),
            'correct': forms.Select(attrs={'class': 'inp'}),
        }


# ===================== Helpers =====================
def get_offering_or_404(term_id, subject_id):
    return get_object_or_404(SubjectOffering, term_id=term_id, subject_id=subject_id)


# ===================== قائمة الدروس + CRUD =====================
def lessons_list_view(request, term_id, subject_id):
    offering = get_offering_or_404(term_id, subject_id)
    lessons = (
        offering.lessons
        .annotate(question_count=Count('questions', distinct=True))  # ← عدد الأسئلة لكل درس
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


# ===================== إدارة الدرس (تحرير محتوى + أسئلة) =====================
def lesson_manage_view(request, term_id, subject_id, lesson_id):
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

    # إضافة سؤال
    if request.method == 'POST' and request.POST.get('form_name') == 'add_question':
        qform = QuestionForm(request.POST)
        if qform.is_valid():
            q = qform.save(commit=False)
            q.lesson = lesson
            q.save()
            return redirect('lesson_manage', term_id=term_id, subject_id=subject_id, lesson_id=lesson_id)
    else:
        qform = QuestionForm()

    # تعديل سؤال
    if request.method == 'POST' and request.POST.get('form_name', '').startswith('edit_question_'):
        qid = request.POST.get('question_id')
        qobj = get_object_or_404(Question, id=qid, lesson=lesson)
        qedit = QuestionForm(request.POST, instance=qobj)
        if qedit.is_valid():
            qedit.save()
            return redirect('lesson_manage', term_id=term_id, subject_id=subject_id, lesson_id=lesson_id)

    # حذف سؤال
    if request.method == 'POST' and request.POST.get('form_name') == 'delete_question':
        qid = request.POST.get('question_id')
        qobj = get_object_or_404(Question, id=qid, lesson=lesson)
        qobj.delete()
        return redirect('lesson_manage', term_id=term_id, subject_id=subject_id, lesson_id=lesson_id)

    questions = lesson.questions.order_by('section', 'id')

    return render(request, 'lesson_manage.html', {
        'offering': offering,
        'term': offering.term,
        'subject': offering.subject,
        'lesson': lesson,
        'cform': cform,
        'qform': qform,
        'questions': questions,
        'SECTION_CHOICES': SECTION_CHOICES,
    })


# ===================== العرض الحقيقي (قراءة فقط) =====================
def lesson_detail_view(request, term_id, subject_id, lesson_id):
    """يعرض محتوى الدرس + يسمح بتحريره الخفيف (Bold/تنظيف) وحفظه."""
    offering = get_offering_or_404(term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)
    # تأكد من وجود كائن المحتوى
    content, _ = LessonContent.objects.get_or_create(lesson=lesson)

    if request.method == 'POST' and request.POST.get('form_name') == 'save_content':
        body_html = request.POST.get('body_html', '').strip()
        # ملاحظة أمنية: هذا HTML سيُعرض بـ |safe في القالب. لا تلصق HTML غير موثوق من مصادر خارجية.
        content.body = body_html
        content.save()
        return redirect('lesson_detail', term_id=term_id, subject_id=subject_id, lesson_id=lesson_id)

    return render(request, 'lesson_detail.html', {
        'offering': offering,
        'term': offering.term,
        'subject': offering.subject,
        'lesson': lesson,
        'content': content,  # مضمون HTML
    })



def lesson_questions_view(request, term_id, subject_id, lesson_id):
    """
    عرض أسئلة الدرس مع دعم نطاق القسم:
    - FULL  => FIRST + SECOND + FULL
    - FIRST => FIRST + FULL
    - SECOND=> SECOND + FULL
    """
    offering = get_offering_or_404(term_id, subject_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, offering=offering)

    # استقبل القسم المختار من GET أو POST (أثناء التصحيح)
    section = request.GET.get('section') or request.POST.get('section') or 'FULL'

    base_qs = lesson.questions.all()
    if section == 'FIRST':
        qs = base_qs.filter(section__in=['FIRST', 'FULL'])
    elif section == 'SECOND':
        qs = base_qs.filter(section__in=['SECOND', 'FULL'])
    else:  # FULL أو أي قيمة غير معروفة
        section = 'FULL'
        qs = base_qs.filter(section__in=['FIRST', 'SECOND', 'FULL'])

    questions = list(qs.order_by('section', 'id'))

    graded = False
    score = 0
    total = len(questions)

    if request.method == 'POST' and request.POST.get('form_name') == 'grade':
        graded = True
        for q in questions:
            sel_raw = request.POST.get(f"q_{q.id}", "")
            try:
                sel = int(sel_raw)
            except ValueError:
                sel = 0
            q.selected = sel
            q.is_correct_flag = (sel == q.correct)
            if q.is_correct_flag:
                score += 1

    return render(request, 'lesson_questions.html', {
        'offering': offering,
        'term': offering.term,
        'subject': offering.subject,
        'lesson': lesson,
        'questions': questions,
        'graded': graded,
        'score': score,
        'total': total,
        'section': section,           # <-- نمرّر القسم المختار للقالب
        'SECTION_CHOICES': SECTION_CHOICES,
    })


