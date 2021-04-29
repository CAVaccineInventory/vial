from django.db import models


class CharTextField(models.CharField):
    def __init__(self, *args, db_collation=None, **kwargs):
        kwargs.setdefault("max_length", 65000)
        super().__init__(*args, db_collation, **kwargs)

    def db_type(self, connection):
        return "text"

    def get_internal_type(self):
        return "CharTextField"
