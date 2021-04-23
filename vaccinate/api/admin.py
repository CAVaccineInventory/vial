from django.contrib import admin
from django.utils.safestring import mark_safe
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


class YourKeysFilter(admin.SimpleListFilter):
    title = "Your keys"
    parameter_name = "yours"

    def lookups(self, request, model_admin):
        return (("yours", "Yours"),)

    def queryset(self, request, queryset):
        if self.value() == "yours":
            return queryset.filter(user=request.user)
        return queryset


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("__str__", "created_at", "user", "description", "last_seen_at")
    list_filter = ("last_seen_at", YourKeysFilter)
    exclude = ("key",)
    readonly_fields = ("user", "created_at", "last_seen_at")
    raw_id_fields = ("user",)

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj and request.user.is_superuser:
            return ("created_at", "last_seen_at")
        if obj and obj.user == request.user:
            return self.readonly_fields + ("key_to_use",)
        if obj and obj.user != request.user:
            # You can't edit other people's keys
            return self.readonly_fields + ("description",)
        return self.readonly_fields

    def key_to_use(self, instance):
        return mark_safe(
            '<h1 class="copy-to-clipboard">{}:{}</h1>'.format(instance.pk, instance.key)
        )


@admin.register(Switch)
class SwitchAdmin(CompareVersionAdmin):
    list_display = ("name", "on", "description")
    readonly_fields = ("name",)
