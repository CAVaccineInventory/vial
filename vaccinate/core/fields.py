from django.db import models


class CharTextField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 65000)
        super(models.CharField, self).__init__(*args, **kwargs)

    def db_type(self, connection):
        return "text"

    def get_internal_type(self):
        return "CharTextField"
