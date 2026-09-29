from django.urls import path

from chat import views

urlpatterns = [
    path('new/', views.new_chat, name='chat_new'),
    path('<int:pk>/', views.session_detail, name='chat_session'),
    path('<int:pk>/delete/', views.delete_session, name='chat_delete'),
]
