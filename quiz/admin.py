from django.contrib import admin
from django.contrib.admin.helpers import ActionForm
from django import forms

from .models import Question, QuizAttempt, UserAnswer


class QuestionAdminActionForm(ActionForm):
    new_category = forms.CharField(
        required=False,
        label='Category to apply',
        help_text='Enter a category name to apply to the selected questions.',
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    action_form = QuestionAdminActionForm
    list_display = ('category', 'text', 'correct_option')
    list_filter = ('category',)
    search_fields = ('category', 'text')
    actions = ['set_category']

    @admin.action(description='Set category for selected questions')
    def set_category(self, request, queryset):
        new_category = request.POST.get('new_category', '').strip()
        if not new_category:
            self.message_user(request, 'Enter a category name before running this action.', level='error')
            return

        updated = queryset.update(category=new_category)
        self.message_user(request, f'Updated {updated} question(s) to category "{new_category}".')


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'score', 'created_at')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('quiz_attempt', 'question', 'selected_option')
    search_fields = ('question__text',)