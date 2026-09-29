from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from chat.forms import NewChatForm
from chat.models import ChatSession
from chat.services import ChatError, start_session
from proxy.errors import ProxyError


def render_chat(request, template, context):
    """Render a chat page with the sidebar's session list."""
    context = {
        'sessions': request.user.chat_sessions.all(),
        'current_session': None,
        **context,
    }
    return render(request, template, context)


@login_required
@require_safe
def home(request):
    return render_chat(request, 'chat/new.html', {'form': NewChatForm(request.user)})


@login_required
@require_POST
def new_chat(request):
    form = NewChatForm(request.user, request.POST)
    error = None
    if form.is_valid():
        try:
            session = start_session(
                request.user,
                form.cleaned_data['llm_model'],
                form.cleaned_data['billing_account'],
                form.cleaned_data['message'],
            )
        except (ChatError, ProxyError) as e:
            error = e.user_message
        else:
            return redirect('chat_session', session.pk)
    # The form is shown again with the text kept, so the user can resend.
    return render_chat(request, 'chat/new.html', {'form': form, 'error': error})


@login_required
@require_safe
def session_detail(request, pk):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)
    return render_chat(request, 'chat/session.html', {
        'current_session': session,
        'chat_messages': session.messages.all(),
    })
