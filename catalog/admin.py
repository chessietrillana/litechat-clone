from django.contrib import admin

from catalog.models import LLMModel


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'provider', 'tier', 'proxy_model_id', 'is_active']
    list_editable = ['is_active']
    list_filter = ['provider', 'tier', 'is_active']
    search_fields = ['display_name', 'proxy_model_id']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['turn_on', 'turn_off']

    # Chat sessions will point at models, so turn models off instead of deleting them.
    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Turn on selected models')
    def turn_on(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'Turned on {count} model(s).')

    @admin.action(description='Turn off selected models')
    def turn_off(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Turned off {count} model(s).')
