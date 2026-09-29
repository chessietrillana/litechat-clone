from django.contrib import admin

from billing.units import format_credits
from chat.models import ChatMessage, ChatSession


class DeletedByUserFilter(admin.SimpleListFilter):
    title = 'deleted by user'
    parameter_name = 'deleted'

    def lookups(self, request, model_admin):
        return [('yes', 'Yes'), ('no', 'No')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(hidden_at__isnull=False)
        if self.value() == 'no':
            return queryset.filter(hidden_at__isnull=True)
        return queryset


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = [
        'created_at', 'role', 'content', 'input_tokens', 'output_tokens', 'cached_tokens',
        'cost', 'finish_reason', 'response_id',
    ]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('charge')

    @admin.display(description='Cost (credits)')
    def cost(self, message):
        return '' if message.cost_micro is None else format_credits(message.cost_micro)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """View only. Sessions are made and changed by users in the chat pages."""
    list_display = ['title', 'user', 'llm_model', 'billing_account', 'created_at', 'updated_at', 'hidden_at']
    list_filter = ['llm_model', DeletedByUserFilter]
    list_select_related = ['user', 'llm_model', 'billing_account__owner']
    search_fields = ['title', 'user__username']
    inlines = [ChatMessageInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
