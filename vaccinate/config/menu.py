from admin_tools.menu import Menu, items
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class CustomMenu(Menu):
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)
        self.children += [
            items.MenuItem(_("Home"), reverse("admin:index")),
            items.AppList(_("Applications"), exclude=("django.contrib.*",)),
            items.AppList(_("Administration"), models=("django.contrib.*",)),
            items.Bookmarks(),
        ]
