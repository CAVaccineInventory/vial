from typing import Dict

import beeline
from django.db import connection
from django.db.models.query import QuerySet


class BaseExpansion:
    def prepare_queryset(self, queryset: QuerySet) -> QuerySet:
        # This can be used to add select_related/prefetch_related
        return queryset

    def expand(self, records) -> Dict:
        # Return a dictionary of record_id => extra keys
        return {}


class VaccineFinderInventoryExpansion(BaseExpansion):
    VACCINE_FINDER_NAMES = {
        # If this string exists, assume this:
        "Moderna": "Moderna",
        "Pfizer": "Pfizer",
        "Johnson": "Johnson & Johnson",
    }
    key = "vaccine_finder_inventory"

    def __init__(self, load_all=False):
        if load_all:
            self.preloaded = self.load_inventory()
        else:
            self.preloaded = None

    @classmethod
    def _extract_vaccine(cls, name):
        for needle, result in cls.VACCINE_FINDER_NAMES.items():
            if needle in name:
                return result
        return None

    @beeline.traced("_vaccinefinder_data_for_locations")
    def load_inventory(self, location_ids=None):
        sql = """
            select
            location.public_id,
            json_extract_path(source_location.import_json::json, 'source', 'data', 'inventory')
            from source_location
              join location
                on location.id = source_location.matched_location_id
        """
        if location_ids:
            sql += "where matched_location_id in (select id from location where public_id in ({}))".format(
                ", ".join("'{}'".format(id) for id in location_ids)
            )
        id_to_vaccines = {}
        with connection.cursor() as cursor:
            cursor.execute(sql)
            for id, inventory in cursor.fetchall():
                if not inventory:
                    continue
                in_stock_vaccines = [
                    self._extract_vaccine(item["name"])
                    for item in inventory
                    if self._extract_vaccine(item["name"])
                    and item["in_stock"] == "TRUE"
                ]
                id_to_vaccines[id] = in_stock_vaccines
        return id_to_vaccines

    def expand(self, records) -> Dict:
        # Return a dictionary of record_id => extra keys
        id_to_vaccines = self.preloaded
        ids = [r["id"] for r in records]
        if id_to_vaccines is None:
            id_to_vaccines = self.load_inventory(location_ids=ids)
        return {id: id_to_vaccines.get(id) for id in ids}
