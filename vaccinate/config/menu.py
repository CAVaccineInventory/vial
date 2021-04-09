from admin_tools.menu import Menu, items
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class ToolsMenu(items.MenuItem):
    title = "Tools"

    def init_with_context(self, context):
        user = context["request"].user
        self.children.append(
            items.MenuItem("API documentation", "/api/docs"),
        )
        if user.has_perm("django_sql_dashboard.execute_sql"):
            self.children.append(
                items.MenuItem("SQL Dashboard", "/dashboard/"),
            )
        if user.has_perm("core.merge_locations"):
            self.children.append(
                items.MenuItem("Merge locations", "/admin/merge-locations/"),
            )
        if user.is_superuser:
            self.children.append(
                items.MenuItem("Data import tools", "/admin/tools/"),
            )
            self.children.append(
                items.MenuItem("Bulk delete reports", "/admin/bulk-delete-reports/"),
            )

    def is_empty(self):
        return not bool(self.children)


class CustomMenu(Menu):
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)
        self.children += [
            items.MenuItem(_("Home"), reverse("admin:index")),
            ToolsMenu(),
            items.AppList(_("Applications"), exclude=("django.contrib.*",)),
            items.AppList(_("Administration"), models=("django.contrib.*",)),
            items.Bookmarks(),
        ]
