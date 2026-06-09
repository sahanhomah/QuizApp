from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Question, QuizAttempt, UserAnswer

QUIZ_LENGTH = 20
SESSION_ATTEMPT_ID = 'quiz_attempt_id'
SESSION_QUESTION_IDS = 'quiz_question_ids'
SESSION_CURRENT_INDEX = 'quiz_current_index'


def home_view(request):
    if request.user.is_authenticated:
        return redirect('quiz:start')

    return render(request, 'quiz/home.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('quiz:start')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully.')
            return redirect('quiz:start')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('quiz:home')


@login_required
def start_quiz(request):
    if request.method == 'POST':
        selected_category = request.POST.get('category', '').strip()
        questions = Question.objects.all()
        if selected_category:
            questions = questions.filter(category=selected_category)

        question_ids = list(questions.order_by('?').values_list('id', flat=True)[:QUIZ_LENGTH])
        if len(question_ids) < QUIZ_LENGTH:
            category_message = f' in category "{selected_category}"' if selected_category else ''
            messages.error(
                request,
                f'You need at least {QUIZ_LENGTH} questions{category_message} to start a quiz.',
            )
            return redirect('quiz:start')

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(user=request.user if request.user.is_authenticated else None)

        request.session[SESSION_ATTEMPT_ID] = attempt.id
        request.session[SESSION_QUESTION_IDS] = question_ids
        request.session[SESSION_CURRENT_INDEX] = 0
        request.session['quiz_category'] = selected_category
        request.session.modified = True
        return redirect('quiz:question')

    categories = list(
        Question.objects.order_by('category').values_list('category', flat=True).distinct()
    )
    return render(
        request,
        'quiz/start.html',
        {
            'question_count': Question.objects.count(),
            'categories': categories,
        },
    )


def _get_active_attempt(request):
    attempt_id = request.session.get(SESSION_ATTEMPT_ID)
    question_ids = request.session.get(SESSION_QUESTION_IDS)
    current_index = request.session.get(SESSION_CURRENT_INDEX, 0)

    if not attempt_id or not question_ids:
        return None, None, None

    attempt = get_object_or_404(QuizAttempt, pk=attempt_id)
    return attempt, question_ids, current_index


@login_required
def question_view(request):
    attempt, question_ids, current_index = _get_active_attempt(request)
    if attempt is None:
        messages.info(request, 'Start a new quiz to begin.')
        return redirect('quiz:start')

    if current_index >= len(question_ids):
        return redirect('quiz:result')

    question = get_object_or_404(Question, pk=question_ids[current_index])
    existing_answer = UserAnswer.objects.filter(quiz_attempt=attempt, question=question).first()

    context = {
        'attempt': attempt,
        'question': question,
        'current_number': current_index + 1,
        'total_questions': len(question_ids),
        'existing_answer': existing_answer,
        'answer_choices': Question.OPTION_CHOICES,
    }
    return render(request, 'quiz/question.html', context)


@login_required
def submit_answer(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method.')

    attempt, question_ids, current_index = _get_active_attempt(request)
    if attempt is None:
        messages.error(request, 'Your quiz session has expired. Start a new quiz.')
        return redirect('quiz:start')

    if current_index >= len(question_ids):
        return redirect('quiz:result')

    selected_option = request.POST.get('selected_option')
    if selected_option not in {'A', 'B', 'C', 'D'}:
        messages.error(request, 'Please choose one of the four options before continuing.')
        return redirect('quiz:question')

    question = get_object_or_404(Question, pk=question_ids[current_index])

    UserAnswer.objects.update_or_create(
        quiz_attempt=attempt,
        question=question,
        defaults={'selected_option': selected_option},
    )

    request.session[SESSION_CURRENT_INDEX] = current_index + 1
    request.session.modified = True

    if current_index + 1 >= len(question_ids):
        return redirect('quiz:result')
    return redirect('quiz:question')


@login_required
def result_view(request):
    attempt, question_ids, current_index = _get_active_attempt(request)
    if attempt is None:
        messages.info(request, 'No active quiz result is available.')
        return redirect('quiz:start')

    if current_index < len(question_ids):
        return redirect('quiz:question')

    questions = Question.objects.filter(id__in=question_ids)
    question_map = {question.id: question for question in questions}
    user_answers = {answer.question_id: answer for answer in attempt.answers.select_related('question')}

    summary = []
    score = 0

    for question_id in question_ids:
        question = question_map.get(question_id)
        if question is None:
            continue
        answer = user_answers.get(question_id)
        selected_option = answer.selected_option if answer else None
        is_correct = selected_option == question.correct_option
        if is_correct:
            score += 1

        option_text_map = {
            'A': question.option_a,
            'B': question.option_b,
            'C': question.option_c,
            'D': question.option_d,
        }

        summary.append(
            {
                'question': question,
                'selected_option': selected_option,
                'selected_answer_text': option_text_map.get(selected_option, 'Not answered'),
                'correct_option': question.correct_option,
                'correct_answer_text': option_text_map[question.correct_option],
                'is_correct': is_correct,
            }
        )

    attempt.score = score
    attempt.save(update_fields=['score'])

    return render(
        request,
        'quiz/result.html',
        {
            'attempt': attempt,
            'summary': summary,
            'score': score,
            'total_questions': len(summary),
        },
    )


@login_required
def leaderboard_view(request):
    attempts = (
        QuizAttempt.objects.select_related('user')
        .order_by('-score', 'created_at')[:10]
    )

    return render(
        request,
        'quiz/leaderboard.html',
        {
            'attempts': attempts,
        },
    )