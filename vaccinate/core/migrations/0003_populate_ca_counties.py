from django.db import migrations

counties = {
    "06001": "Alameda",
    "06003": "Alpine",
    "06005": "Amador",
    "06007": "Butte",
    "06009": "Calaveras",
    "06011": "Colusa",
    "06013": "Contra Costa",
    "06015": "Del Norte",
    "06017": "El Dorado",
    "06019": "Fresno",
    "06021": "Glenn",
    "06023": "Humboldt",
    "06025": "Imperial",
    "06027": "Inyo",
    "06029": "Kern",
    "06031": "Kings",
    "06033": "Lake",
    "06035": "Lassen",
    "06037": "Los Angeles",
    "06039": "Madera",
    "06041": "Marin",
    "06043": "Mariposa",
    "06045": "Mendocino",
    "06047": "Merced",
    "06049": "Modoc",
    "06051": "Mono",
    "06053": "Monterey",
    "06055": "Napa",
    "06057": "Nevada",
    "06059": "Orange",
    "06061": "Placer",
    "06063": "Plumas",
    "06065": "Riverside",
    "06067": "Sacramento",
    "06069": "San Benito",
    "06071": "San Bernardino",
    "06073": "San Diego",
    "06075": "San Francisco",
    "06077": "San Joaquin",
    "06079": "San Luis Obispo",
    "06081": "San Mateo",
    "06083": "Santa Barbara",
    "06085": "Santa Clara",
    "06087": "Santa Cruz",
    "06089": "Shasta",
    "06091": "Sierra",
    "06093": "Siskiyou",
    "06095": "Solano",
    "06097": "Sonoma",
    "06099": "Stanislaus",
    "06101": "Sutter",
    "06103": "Tehama",
    "06105": "Trinity",
    "06107": "Tulare",
    "06109": "Tuolumne",
    "06111": "Ventura",
    "06113": "Yolo",
    "06115": "Yuba",
}


def populate_counties(apps, schema_editor):
    State = apps.get_model("core", "State")
    ca = State.objects.get(abbreviation="CA")
    for fips, name in counties.items():
        ca.counties.create(fips_code=fips, name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_populate_states"),
    ]

    operations = [migrations.RunPython(populate_counties)]
