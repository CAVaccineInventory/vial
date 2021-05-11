import reversion


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


def merge_locations(winner, loser, user):
    with reversion.create_revision():
        loser.reports.update(location=winner.pk)
        loser.soft_deleted = True
        loser.soft_deleted_because = "Merged into location {}".format(winner.public_id)
        loser.duplicate_of = winner
        loser.save()
        reversion.set_user(user)
        reversion.set_comment(
            "Merged locations, winner = {}, loser = {}".format(
                winner.public_id, loser.public_id
            )
        )
