from difflib import SequenceMatcher

import re


BASE_WEIGHTS = {

    "category": 20,

    "title": 15,

    "brand": 15,

    "model": 15,

    "color": 10,

    "location": 15,

    "date": 5,

    "time": 5,

}


def clean(value):

    if value is None:

        return ""

    value = str(value).lower()

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def similarity(a, b):

    a = clean(a)

    b = clean(b)

    if not a or not b:

        return None

    if a == b:

        return 1.0

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


def calculate_match(
    lost,
    found
):

    fields = {

        "category": (
            lost.category,
            found.category
        ),

        "title": (
            lost.title,
            found.title
        ),

        "brand": (
            lost.brand,
            found.brand
        ),

        "model": (
            lost.model,
            found.model
        ),

        "color": (
            lost.color,
            found.color
        ),

        "location": (
            lost.location,
            found.location
        ),

        "date": (
            lost.lost_date,
            found.found_date
        ),

        "time": (
            lost.lost_time,
            found.found_time
        )
    }

    available = []

    for field, values in fields.items():

        score = similarity(
            values[0],
            values[1]
        )

        if score is not None:

            available.append(
                (
                    field,
                    BASE_WEIGHTS[field],
                    score
                )
            )

    if not available:

        return 0, []

    total_weight = sum(
        x[1]
        for x in available
    )

    final_score = 0

    details = []

    for field, weight, score in available:

        normalized_weight = (
            weight / total_weight
        )

        contribution = (
            score
            * normalized_weight
            * 100
        )

        final_score += contribution

        details.append({

            "field": field,

            "weight": round(
                normalized_weight * 100,
                2
            ),

            "similarity": round(
                score * 100,
                2
            )

        })

    return round(
        final_score,
        2
    ), details