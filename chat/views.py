from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from chat.forms import MessageForm, NewChatForm
from chat.models import ChatSession
from chat.services import NO_CREDITS, ChatError, send_turn, start_session
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
@require_http_methods(['GET', 'HEAD', 'POST'])
def session_detail(request, pk):
    """GET shows the session. POST sends the next message."""
    session = get_object_or_404(
        ChatSession.objects.select_related('llm_model', 'billing_account__owner'),
        pk=pk, user=request.user,
    )
    error = None
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            try:
                send_turn(session, form.cleaned_data['message'])
            except (ChatError, ProxyError) as e:
                error = e.user_message
            else:
                return redirect('chat_session', session.pk)
    else:
        form = MessageForm()
    balance = session.billing_account.balance_micro()
    out_of_credits = balance <= 0
    if out_of_credits and error == NO_CREDITS:
        error = None  # The page already says so in place of the input box.
    totals = session.messages.aggregate(tokens=Sum('charge__tokens'), cost=Sum('charge__amount_micro'))
    return render_chat(request, 'chat/session.html', {
        'current_session': session,
        'chat_messages': session.messages.select_related('charge'),
        'total_tokens': totals['tokens'] or 0,
        'total_cost': -(totals['cost'] or 0),
        'form': form,
        'error': error,
        'balance': balance,
        'out_of_credits': out_of_credits,
    })
