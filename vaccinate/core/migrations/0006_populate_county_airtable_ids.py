from django.db import migrations


counties = {
    "Glenn": "rec0QOd7EXzSuZZvN",
    "Shasta": "rec1rvcyGSS6AgQEq",
    "Tuolumne": "rec1wHp8vuiDzVdMw",
    "Sonoma": "rec21xHBYYJxXXOiq",
    "Santa Clara": "rec2V4GnfzE4qF2a0",
    "Madera": "rec2j4TlWO7zJT5AE",
    "Yuba": "rec5FGk70LKjdkynb",
    "Humboldt": "rec7kL5TGBqWVlkHm",
    "Monterey": "rec7vkrMOgPeUg6Z2",
    "Santa Cruz": "rec8EEJmJzCdopVzu",
    "Alameda": "rec8Jdl4558rVpGc5",
    "San Joaquin": "recAJsHK8yXnzdl6w",
    "Tehama": "recFTYWXSD4kd17eo",
    "Mariposa": "recFriRxcb5aA4Crq",
    "Yolo": "recGbLZ8Ng6aB3SF9",
    "Napa": "recJ1fLYsngDaIRLG",
    "San Francisco": "recOuBZk28GMl7mVw",
    "San Luis Obispo": "recMD5hrJf1iGh0On",
    "Butte": "recMF4xBLqll2wYtk",
    "San Mateo": "recMxizpwIMytvJ2r",
    "Sutter": "recNTl8pzOr57Ql1d",
    "Mono": "recOtOQyjwtIAB9vs",
    "Contra Costa": "recP7bxtLsyO94BOI",
    "Sierra": "recQYGuJuebVYxg7I",
    "Siskiyou": "recSgrpyStTR7XfmZ",
    "Imperial": "recTuH0G20ua9ErUU",
    "Inyo": "recVCgGTLt7PpNSkb",
    "Kings": "recVhw3mOj2KaUWvx",
    "Nevada": "recY8ARCBGpH545Jv",
    "Los Angeles": "recZNvS1ogJzGOPgG",
    "Trinity": "recafMhaFNhRpDlFR",
    "Orange": "recarUDlLAO0MtvA7",
    "Stanislaus": "recb6ibrCGCw71RbX",
    "Sacramento": "recbziYEC1C89DvF3",
    "San Benito": "reccGVb82uJTXcyzA",
    "Marin": "recfGCTuJg8X3CHzK",
    "Lake": "recgAENHoupyViJxe",
    "Ventura": "recgC68ghhJW0EDz4",
    "Calaveras": "rechyq0ZDsgfqek3O",
    "Tulare": "recipKOzQdBxv0mAf",
    "Del Norte": "reciwvE3uydUJmPr9",
    # "Napa ": "recjptepZLP1mzVDC",
    "Merced": "recl8GEIaG1m1qokG",
    "San Bernardino": "reclZ8DWOEuoluStG",
    "San Diego": "recm5wnoHs38ZYhzu",
    "Lassen": "recmEBjsHW6t9GDHg",
    "Placer": "recmKHVjaO9gDpzN7",
    "Colusa": "recnWwqVyXQCTDOAJ",
    "Kern": "recoq6vXe53Z3Tnbw",
    "El Dorado": "recq5HeJCFHGSIzrq",
    "Mendocino": "rectD96YQWb5CnHV4",
    "Plumas": "rectLKwoh8OStFdqH",
    "Solano": "rectXRYX9gh3dALJJ",
    "Santa Barbara": "recuweSK9OqJ7C2l4",
    "Riverside": "recvQcNeuIr14uskB",
    "Modoc": "recwQTax8QogfC8kF",
    "Amador": "recxImnEbGNQGidKW",
    "Alpine": "recyKBuA9lxrJc339",
    "Fresno": "reczthUUHssxaQj7X",
}


def populate_county_airtable_ids(apps, schema_editor):
    County = apps.get_model("core", "County")
    # Assert that all of the names exist
    existing = set(
        County.objects.filter(
            name__in=counties.keys(), state__abbreviation="CA"
        ).values_list("name", flat=True)
    )
    missing = [c for c in counties if c not in existing]
    assert not missing, "Missing counties: " + str(missing)
    for name, airtable_id in counties.items():
        c = County.objects.get(name=name, state__abbreviation="CA")
        assert c.airtable_id is None
        c.airtable_id = airtable_id
        c.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_airtable_id_columns"),
    ]

    operations = [migrations.RunPython(populate_county_airtable_ids)]
