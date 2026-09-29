from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.views import SignUpView

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    # LogoutView accepts POST only (Django 5+).
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
