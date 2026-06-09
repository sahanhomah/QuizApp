from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django import forms
import difflib
from django.db.models import Count

from .models import Question, QuizAttempt, UserAnswer


class QuestionAdminActionForm(ActionForm):
    new_category = forms.CharField(
        required=False,
        label='Category to apply',
        help_text='Enter a category name to apply to the selected questions.',
    )
    similarity_threshold = forms.FloatField(
        required=False,
        initial=0.85,
        label='Similarity threshold',
        help_text='A value between 0 and 1 used to detect similar category names (higher = stricter).',
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    action_form = QuestionAdminActionForm
    list_display = ('category', 'text', 'correct_option')
    list_filter = ('category',)
    search_fields = ('category', 'text')
    actions = ['set_category', 'merge_similar_categories']

    # Admin action to detect similar category names and merge them
    @admin.action(description='Detect and merge similar category names')
    def merge_similar_categories(self, request, queryset):
        # Use categories from the selected queryset if provided, else consider all categories
        source_qs = queryset if queryset.exists() else Question.objects.all()
        categories = list(source_qs.order_by('category').values_list('category', flat=True).distinct())
        try:
            threshold = float(request.POST.get('similarity_threshold') or 0.85)
        except (TypeError, ValueError):
            threshold = 0.85

        visited = set()
        groups = []
        for cat in categories:
            if cat in visited:
                continue
            matches = difflib.get_close_matches(cat, categories, n=50, cutoff=threshold)
            matches = [m for m in matches if m not in visited]
            if len(matches) > 1:
                groups.append(matches)
            for m in matches:
                visited.add(m)

        if not groups:
            self.message_user(request, 'No similar category groups found.', level=messages.INFO)
            return

        total_updated = 0
        details = []
        for group in groups:
            counts = Question.objects.filter(category__in=group).values('category').annotate(cnt=Count('id')).order_by('-cnt')
            canonical = counts[0]['category']
            for cat in group:
                if cat == canonical:
                    continue
                updated = Question.objects.filter(category=cat).update(category=canonical)
                if updated:
                    total_updated += updated
                    details.append(f'Changed {updated} from "{cat}" to "{canonical}"')

        msg = f'Merge complete. {total_updated} rows updated across {len(groups)} group(s).'
        if details:
            msg = msg + ' Details: ' + '; '.join(details)
        self.message_user(request, msg)

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