from difflib import SequenceMatcher

import re


DEFAULT_WEIGHTS = {

    "unique_mark": 30,

    "accessory": 25,

    "damage": 20,

    "custom_feature": 20,

    "engraving": 25,

    "sticker": 20,

    "contents": 20,

    "brand_model": 20,

    "other": 10

}


QUESTIONS = {

    "unique_mark":
        "What unique mark or identifying detail does the item have?",

    "accessory":
        "What accessory was attached to or kept with the item?",

    "damage":
        "What scratch, crack, damage or unusual feature does the item have?",

    "custom_feature":
        "What custom feature or modification does the item have?",

    "engraving":
        "What engraving, writing or text is present on the item?",

    "sticker":
        "What sticker or label is present on the item?",

    "contents":
        "What specific contents or configuration did the item have?",

    "brand_model":
        "What exact brand or model does the item have?",

    "other":
        "Tell us another specific identifying detail of the item."

}


def clean_text(text):

    if not text:

        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def compare_answer(
    claimant_answer,
    secret_answer
):

    if not claimant_answer or not secret_answer:

        return 0.0

    answer = clean_text(
        claimant_answer
    )

    secret = clean_text(
        secret_answer
    )

    if not answer or not secret:

        return 0.0

    # Prevent simple contradiction such as:
    # secret = "blue sticker"
    # answer = "no blue sticker"

    negations = {
        "no",
        "not",
        "never",
        "without",
        "none",
        "dont",
        "don't"
    }

    answer_words = set(
        answer.split()
    )

    secret_words = set(
        secret.split()
    )

    if bool(answer_words & negations) != bool(
        secret_words & negations
    ):

        return 0.0

    if answer == secret:

        return 1.0

    common = (
        answer_words
        & secret_words
    )

    union = (
        answer_words
        | secret_words
    )

    word_score = (
        len(common)
        / len(union)
        if union
        else 0
    )

    sentence_score = SequenceMatcher(
        None,
        answer,
        secret
    ).ratio()

    return max(
        0,
        min(
            1,
            (
                sentence_score * 0.6
                +
                word_score * 0.4
            )
        )
    )


def get_weight(evidence):

    if (
        evidence.base_weight
        and float(evidence.base_weight) != 1
    ):

        return float(
            evidence.base_weight
        )

    return DEFAULT_WEIGHTS.get(
        evidence.evidence_type,
        10
    )


def generate_question(
    evidence_type
):

    return QUESTIONS.get(
        evidence_type,
        QUESTIONS["other"]
    )


def verify_ownership(
    evidences,
    answers
):

    available = [

        evidence

        for evidence in evidences

        if (
            evidence.is_active
            and evidence.secret_value
        )

    ]

    if not available:

        return {

            "score": 0,

            "status":
                "ADDITIONAL_VERIFICATION_REQUIRED",

            "details": []

        }

    total_weight = sum(
        get_weight(e)
        for e in available
    )

    final_score = 0

    details = []

    for evidence in available:

        answer = answers.get(
            evidence.id,
            ""
        )

        similarity = compare_answer(
            answer,
            evidence.secret_value
        )

        normalized_weight = (
            get_weight(evidence)
            / total_weight
        )

        contribution = (
            similarity
            * normalized_weight
            * 100
        )

        if similarity >= 0.85:

            level = "STRONG"

        elif similarity >= 0.65:

            level = "GOOD"

        elif similarity >= 0.40:

            level = "PARTIAL"

        else:

            level = "WEAK"

        final_score += contribution

        details.append({

            "evidence_id":
                evidence.id,

            "evidence_type":
                evidence.evidence_type,

            "weight":
                round(
                    normalized_weight * 100,
                    2
                ),

            "similarity":
                round(
                    similarity * 100,
                    2
                ),

            "contribution":
                round(
                    contribution,
                    2
                ),

            "level":
                level

        })

    final_score = round(
        final_score,
        2
    )

    if final_score >= 80:

        status = "STRONG_EVIDENCE"

    elif final_score >= 60:

        status = (
            "ADDITIONAL_VERIFICATION_REQUIRED"
        )

    else:

        status = "INSUFFICIENT_EVIDENCE"

    return {

        "score": final_score,

        "status": status,

        "details": details

    }