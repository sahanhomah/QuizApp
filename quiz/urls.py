from django.urls import path

from . import views

app_name = 'quiz'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('start/', views.start_quiz, name='start'),
    path('register/', views.register_view, name='register'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('quiz/question/', views.question_view, name='question'),
    path('quiz/submit/', views.submit_answer, name='submit_answer'),
    path('quiz/result/', views.result_view, name='result'),
]