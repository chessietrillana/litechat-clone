from django.urls import path

from catalog.views import model_list

urlpatterns = [
    path('', model_list, name='models'),
]
