import secrets

from core.fields import CharTextField
from django.db import models
from django.utils import timezone


def random_secret():
    return secrets.token_hex(16)


class ApiKey(models.Model):
    created_at = models.DateTimeField(
        default=timezone.now, help_text="When the API key was created"
    )
    user = models.ForeignKey(
        "auth.User",
        related_name="api_keys",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time API key was seen, accurate to within one minute",
    )
    description = models.TextField(help_text="What this API key is being used for")
    key = models.CharField(max_length=32, default=random_secret)

    def token(self):
        return "{}:{}".format(self.id, self.key)

    def __str__(self):
        return "{}:{}...".format(self.pk, self.key[:8])


class ApiLog(models.Model):
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    user = models.ForeignKey(
        "auth.User",
        related_name="api_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    method = CharTextField(help_text="The HTTP method")
    path = CharTextField(help_text="The path, starting with /")
    query_string = CharTextField(blank=True, help_text="The bit after the ?")
    remote_ip = CharTextField()
    post_body = models.BinaryField(
        null=True,
        blank=True,
        help_text="If the post body was not valid JSON, log it here as text",
    )
    post_body_json = models.JSONField(
        null=True, blank=True, help_text="Post body if it was valid JSON"
    )
    response_status = models.IntegerField(
        help_text="HTTP status code returned by the API"
    )
    response_body = models.BinaryField(
        null=True, blank=True, help_text="If the response body was not valid JSON"
    )
    response_body_json = models.JSONField(
        null=True, blank=True, help_text="Response body if it was JSON"
    )
    created_report = models.ForeignKey(
        "core.Report",
        null=True,
        blank=True,
        related_name="created_by_api_logs",
        on_delete=models.SET_NULL,
        help_text="Report that was created by this API call, if any",
    )
    api_key = models.ForeignKey(
        ApiKey, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        db_table = "api_log"

    def __str__(self):
        return "{} {} [{}] - {}".format(
            self.method, self.path, self.response_status, self.created_at
        )


class Switch(models.Model):
    name = models.CharField(max_length=128, unique=True)
    on = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Switches"
