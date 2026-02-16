from django.db import models
from django.conf import settings

class Year(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='years')
    number = models.PositiveSmallIntegerField(choices=[(1, 'السنة الأولى'), (2, 'السنة الثانية')])

    class Meta:
        unique_together = [('owner', 'number')]
        verbose_name = 'سنة'
        verbose_name_plural = 'سنوات'

    def __str__(self):
        return dict(self._meta.get_field('number').choices).get(self.number, str(self.number))


class Term(models.Model):
    year = models.ForeignKey(Year, on_delete=models.CASCADE, related_name='terms')
    number = models.PositiveSmallIntegerField(choices=[(1, 'الفصل الأول'), (2, 'الفصل الثاني')])

    class Meta:
        unique_together = [('year', 'number')]
        verbose_name = 'فصل'
        verbose_name_plural = 'فصول'

    def __str__(self):
        return f"{self.year} - {dict(self._meta.get_field('number').choices).get(self.number)}"


class Subject(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = [('owner', 'name')]
        verbose_name = 'مادة'
        verbose_name_plural = 'مواد'

    def __str__(self):
        return self.name


class SubjectOffering(models.Model):
    """
    ربط "المادة" بـ "الفصل" حتى نستعمل نفس أسماء المواد في كل فصل.
    """
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='offerings')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='offerings')

    class Meta:
        unique_together = [('term', 'subject')]
        verbose_name = 'مادة في فصل'
        verbose_name_plural = 'مواد الفصل'

    def __str__(self):
        return f"{self.subject} ({self.term})"
    @property  # CHANGED: خاصية جاهزة للقالب تُرجع قائمة أيام 0..6
    def sched_days(self):
        """
        يُرجِع قائمة بالأيام (0..6) حسب جداول SubjectSchedule المرتبطة.
        تمثيلنا في SubjectSchedule.weekday هو 0..6 بالفعل (الإثنين=0..الأحد=6)
        """
        # NOTE: استخدام values_list مباشر لتجنب تحميل كائنات كاملة
        days = list(self.schedules.values_list('weekday', flat=True))
        # إزالة التكرارات مع الحفاظ على الترتيب
        return list(dict.fromkeys(days))

    def is_today_for(self, weekday_idx_0_6: int) -> bool:  # CHANGED: دالة مساعدة للحساب
        """هل هذه المادة مقررة لليوم المعطى؟"""
        return weekday_idx_0_6 in self.sched_days
    

SECTION_CHOICES = [
    ('FIRST',  'القسم الأول'),
    ('SECOND', 'القسم الثاني'),
    ('FULL',   'كامل القسم'),
]

class Lesson(models.Model):
    """الدرس داخل مادة مرتبطة بفصل محدد (SubjectOffering)."""
    offering = models.ForeignKey('SubjectOffering', on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField('عنوان الدرس', max_length=200)
    order = models.PositiveIntegerField('الترتيب', default=1)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('offering', 'title')]  # منع تكرار عنوان الدرس داخل نفس المادة/الفصل
        verbose_name = 'درس'
        verbose_name_plural = 'دروس'

    def __str__(self):
        return f"{self.title} — {self.offering}"


class LessonContent(models.Model):
    """محتوى نصّي بسيط لكل درس (يمكن توسيعه لاحقًا)."""
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='content')  # محتوًى واحد لكل درس
    body = models.TextField('المحتوى النصّي', blank=True)

    class Meta:
        verbose_name = 'محتوى الدرس (نص)'
        verbose_name_plural = 'محتوى الدروس (نص)'

    def __str__(self):
        return f"محتوى: {self.lesson}"

class Question(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='questions')
    section = models.CharField('القسم', max_length=10, choices=SECTION_CHOICES, default='FULL')
    text = models.TextField('نص السؤال')

    choice1 = models.CharField('الخيار 1', max_length=300, default='—')
    choice2 = models.CharField('الخيار 2', max_length=300, default='—')
    choice3 = models.CharField('الخيار 3', max_length=300, default='—')

    CORRECT_CHOICES = [(1, 'الخيار 1'), (2, 'الخيار 2'), (3, 'الخيار 3')]
    correct = models.PositiveSmallIntegerField('الإجابة الصحيحة', choices=CORRECT_CHOICES, default=1)


    class Meta:
        verbose_name = 'سؤال'
        verbose_name_plural = 'أسئلة'

    def __str__(self):
        return f"[{self.get_section_display()}] {self.text[:40]}..."
    
class SubjectSchedule(models.Model):
    """
    يوم الأسبوع الذي تُدرَّس فيه المادة داخل هذا الفصل.
    نستخدم أرقام weekday تبع بايثون: الاثنين=0 ... الأحد=6
    """
    WEEKDAYS = [
        (0, 'الاثنين'),
        (1, 'الثلاثاء'),
        (2, 'الأربعاء'),
        (3, 'الخميس'),
        (4, 'الجمعة'),
        (5, 'السبت'),
        (6, 'الأحد'),
    ]

    offering = models.ForeignKey('SubjectOffering', on_delete=models.CASCADE, related_name='schedules')
    weekday  = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    lecture_no = models.PositiveSmallIntegerField(null=True, blank=True, help_text='اختياري: رقم المحاضرة في نفس اليوم')

    class Meta:
        verbose_name = 'جدول مادة (يوم)'
        verbose_name_plural = 'جدول مواد (أيام)'
        # لا نضع unique_together لترك حرية أكثر (أكثر من محاضرة في اليوم)

    def __str__(self):
        return f"{self.offering} - {self.get_weekday_display()}" + (f" #{self.lecture_no}" if self.lecture_no else "")

# --- Weekly quiz models (independent from Lesson) ---

class QuestionType(models.TextChoices):
    MCQ = 'MCQ', 'اختيارات'
    TF  = 'TF',  'صح/خطأ'

class Week(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='weeks')
    number = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('term', 'number')
        ordering = ['term_id', 'number']
    def __str__(self):
        return f"Term {self.term_id} - Week {self.number}"

class WeeklyQuiz(models.Model):
    offering = models.ForeignKey(SubjectOffering, on_delete=models.CASCADE, related_name='weekly_quizzes')
    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200, blank=True)
    is_published = models.BooleanField(default=False)
    class Meta:
        unique_together = ('offering', 'week')
        ordering = ['offering_id', 'week_id']
    def __str__(self):
        return self.title or f"{self.offering.subject.name} - أسبوع {self.week.number}"

class WeeklyQuestion(models.Model):
    quiz = models.ForeignKey(WeeklyQuiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    qtype = models.CharField(max_length=3, choices=QuestionType.choices, default=QuestionType.MCQ)
    # لـ TF فقط:
    correct_bool = models.BooleanField(null=True, blank=True)
    # في حال كانت الإجابة "خطأ" يمكن كتابة الإجابة الصحيحة نصيًا
    correct_text = models.CharField(max_length=255, null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ['order', 'id']

class WeeklyChoice(models.Model):
    question = models.ForeignKey(WeeklyQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ['order', 'id']
