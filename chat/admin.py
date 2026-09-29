from django.contrib import admin

from chat.models import ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = [
        'created_at', 'role', 'content', 'input_tokens', 'output_tokens', 'cached_tokens',
        'finish_reason', 'response_id',
    ]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """View only. Sessions are made and changed by users in the chat pages."""
    list_display = ['title', 'user', 'llm_model', 'billing_account', 'created_at', 'updated_at']
    list_filter = ['llm_model']
    list_select_related = ['user', 'llm_model', 'billing_account__owner']
    search_fields = ['title', 'user__username']
    inlines = [ChatMessageInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
