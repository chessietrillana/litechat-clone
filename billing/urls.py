from django.urls import path

from billing.views import usage

urlpatterns = [
    path('', usage, name='usage'),
]
