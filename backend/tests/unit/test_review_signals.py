from app.scoring.review_signals import extract_amenity_signals, to_amenities_bool


def test_positive_mentions_detected_for_wifi_and_outlets():
    reviews = [
        "Great cafe with fast wifi and plenty of outlets for laptops.",
        "They have a charging port near every table, great for remote work.",
    ]

    signals = extract_amenity_signals(reviews)

    assert signals["wifi"].present is True
    assert signals["wifi"].mention_count == 1  # "wifi" appears once, no overlap with "wi-fi"/"internet"
    assert signals["outlets"].present is True
    assert signals["outlets"].mention_count >= 1
    assert "quiet" not in signals  # no quiet-related keywords in either review


def test_negation_flips_wifi_to_absent():
    reviews = ["Unfortunately there was no wifi available during our stay."]

    signals = extract_amenity_signals(reviews)

    assert signals["wifi"].present is False
    assert signals["wifi"].mention_count == 0
    assert signals["wifi"].negative_mention_count == 1


def test_noisy_counts_as_not_quiet_without_needing_a_negation_word():
    reviews = ["It's way too noisy in here to get any work done."]

    signals = extract_amenity_signals(reviews)

    assert signals["quiet"].present is False
    assert signals["quiet"].mention_count == 0
    assert signals["quiet"].negative_mention_count == 1


def test_no_keyword_mentions_means_amenity_absent_from_result():
    reviews = ["The croissants here are amazing and the staff is super friendly."]

    signals = extract_amenity_signals(reviews)

    assert signals == {}


def test_to_amenities_bool_conversion():
    reviews = ["Fast wifi, no outlets though."]

    signals = extract_amenity_signals(reviews)
    bool_map = to_amenities_bool(signals)

    assert bool_map == {"wifi": True, "outlets": False}


def test_sample_quote_is_captured_for_a_mention():
    reviews = ["The wifi here is blazing fast and reliable for calls."]

    signals = extract_amenity_signals(reviews)

    assert len(signals["wifi"].sample_quotes) == 1
    assert "wifi" in signals["wifi"].sample_quotes[0].lower()
