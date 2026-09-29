from django.contrib import admin

from billing.models import TierPrice


@admin.register(TierPrice)
class TierPriceAdmin(admin.ModelAdmin):
    list_display = ['tier', 'price_per_1k_tokens', 'updated_at']
    list_editable = ['price_per_1k_tokens']
    readonly_fields = ['tier', 'updated_at']

    # Exactly one row per tier, seeded by a migration.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
