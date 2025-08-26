# edu/views.py
from django.forms import ModelForm
from django import forms
from .models import Year, Term, Subject, SubjectOffering, Lesson, LessonContent, Question, SECTION_CHOICES

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
