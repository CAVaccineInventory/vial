from core.fields import CharTextField
from django.db import models
from django.utils import timezone


class ApiLog(models.Model):
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
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

    class Meta:
        db_table = "api_log"

    def __str__(self):
        return "{} {} [{}] - {}".format(
            self.method, self.path, self.response_status, self.created_at
        )
