import reversion
from django.contrib.auth.models import User

from .models import CompletedLocationMerge, ConcordanceIdentifier, Location


def keyset_pagination_iterator(input_queryset, batch_size=500, stop_after=None):
    all_queryset = input_queryset.order_by("pk")
    last_pk = None
    i = 0
    while True:
        queryset = all_queryset
        if last_pk is not None:
            queryset = all_queryset.filter(pk__gt=last_pk)
        queryset = queryset[:batch_size]
        for row in queryset:
            last_pk = row.pk
            yield row
            i += 1
            if stop_after and i >= stop_after:
                return
        if not queryset:
            break


def merge_locations(winner: Location, loser: Location, user: User):
    with reversion.create_revision():
        # Record details of prior state before merge for these things,
        # because they will not be automatically captured in the
        # reversion history for the Location records
        winner_concordances = [str(c) for c in winner.concordances.all()]
        loser_concordances = [str(c) for c in loser.concordances.all()]
        details = {
            "winner_report_ids": list(winner.reports.values_list("pk", flat=True)),
            "loser_report_ids": list(loser.reports.values_list("pk", flat=True)),
            "winner_concordances": winner_concordances,
            "loser_concordances": loser_concordances,
        }
        loser.reports.update(location=winner.pk)
        loser.soft_deleted = True
        loser.soft_deleted_because = "Merged into location {}".format(winner.public_id)
        loser.duplicate_of = winner
        loser.save()

        # Copy concordances from loser to winner
        missing_concordances = [
            c for c in loser_concordances if c not in winner_concordances
        ]
        for concordance in missing_concordances:
            winner.concordances.add(ConcordanceIdentifier.for_idref(concordance))

        CompletedLocationMerge.objects.create(
            winner_location=winner,
            loser_location=loser,
            created_by=user,
            details=details,
        )

        reversion.set_user(user)
        reversion.set_comment(
            "Merged locations, winner = {}, loser = {}".format(
                winner.public_id, loser.public_id
            )
        )
