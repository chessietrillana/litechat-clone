from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from catalog.models import LLMModel


@login_required
def model_list(request):
    return render(request, 'catalog/model_list.html', {'models': LLMModel.objects.active()})
