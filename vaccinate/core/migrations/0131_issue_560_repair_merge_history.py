# https://github.com/CAVaccineInventory/vial/issues/560#issuecomment-840729177
from django.db import migrations
from django.utils import timezone


def concordance_for_idref(cls, idref):
    authority, identifier = idref.split(":", 1)
    return cls.objects.get_or_create(authority=authority, identifier=identifier)[0]


def concordance_str(self):
    return "{}:{}".format(self.authority, self.identifier)


def repair_merge_history(apps, schema_editor):
    # Find all revisions like: 'Merged locations, winner = ldkcp, loser = ldkff'
    Revision = apps.get_model("reversion", "Revision")
    Location = apps.get_model("core", "Location")
    CompletedLocationMerge = apps.get_model("core", "CompletedLocationMerge")
    ConcordanceIdentifier = apps.get_model("core", "ConcordanceIdentifier")
    revisions = Revision.objects.filter(comment__startswith="Merged locations,")
    now = timezone.now()
    for revision in revisions:
        winner_public_id, loser_public_id = revision.comment.split(", winner = ")[
            1
        ].split(", loser = ")
        winner = Location.objects.get(public_id=winner_public_id)
        loser = Location.objects.get(public_id=loser_public_id)

        # Things we need to fix:
        # - Are all concordances from loser on winner?
        # - Have all matched source locations been updated from loser to winner?
        # - Create a CompletedLocationMerge if there is not one yet

        # Are all concordances from loser on winner?
        winner_concordances = [concordance_str(c) for c in winner.concordances.all()]
        loser_concordances = [concordance_str(c) for c in loser.concordances.all()]
        missing_concordances = [
            c for c in loser_concordances if c not in winner_concordances
        ]
        for concordance in missing_concordances:
            winner.concordances.add(
                concordance_for_idref(ConcordanceIdentifier, concordance)
            )

        # Have all matched source locations been updated from loser to winner?
        loser_matched_source_location_ids = None
        winner_matched_source_location_ids = None
        if loser.matched_source_locations.exists():
            winner_matched_source_location_ids = list(
                winner.matched_source_locations.values_list("pk", flat=True)
            )
            loser_matched_source_location_ids = list(
                loser.matched_source_locations.values_list("pk", flat=True)
            )
            loser.matched_source_locations.update(matched_location=winner.pk)

        # Is there already a CompletedLocationMerge for these?
        completed_location_merge = CompletedLocationMerge.objects.filter(
            winner_location__public_id=winner_public_id,
            loser_location__public_id=loser_public_id,
        ).first()

        if not completed_location_merge:
            completed_location_merge = CompletedLocationMerge.objects.create(
                winner_location=winner,
                loser_location=loser,
                created_by=revision.user,
                details={
                    "loser_matched_source_location_ids": loser_matched_source_location_ids,
                    "winner_matched_source_location_ids": winner_matched_source_location_ids,
                    "backfilled_on": now.isoformat(),
                    "backfill_warning": "https://github.com/CAVaccineInventory/vial/issues/560#issuecomment-840759327",
                },
                created_at=revision.date_created,
            )
        else:
            # Add winner_matched_source_location_ids/loser_matched_source_location_ids
            # to details if we made any changes
            if loser_matched_source_location_ids and (
                "loser_matched_source_location_ids"
                not in completed_location_merge.details
            ):
                completed_location_merge.details[
                    "loser_matched_source_location_ids"
                ] = loser_matched_source_location_ids
                completed_location_merge.details[
                    "winner_matched_source_location_ids"
                ] = winner_matched_source_location_ids
                completed_location_merge.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0130_completedlocationmerge"),
    ]

    operations = [
        migrations.RunPython(
            repair_merge_history, reverse_code=lambda apps, schema_editor: None
        )
    ]
