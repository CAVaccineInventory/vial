from django.contrib import admin
from reversion_compare.admin import CompareVersionAdmin

from .models import ApiKey, ApiLog, Switch


@admin.register(ApiLog)
class ApiLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "method",
        "path",
        "response_status",
    )
    list_filter = ("created_at", "method", "response_status", "path")
    raw_id_fields = ("created_report",)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("__str__", "created_at", "last_seen_at", "description")
    list_filter = ("last_seen_at",)
    exclude = ("key",)
    readonly_fields = ("created_at", "last_seen_at", "key_to_use")

    def key_to_use(self, instance):
        return "{}:{}".format(instance.pk or "SAVE-TO-GET-ID", instance.key)


@admin.register(Switch)
class SwitchAdmin(CompareVersionAdmin):
    list_display = ("name", "on")
