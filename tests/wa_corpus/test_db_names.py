from scripts.wa_corpus.db import _distinct_names_in_texts


def test_stopwords_do_not_count_as_names():
    # A normal 1-a-1 chat: only Antonello and Alex are real names.
    texts = [
        "Hi bro, how are you?",
        "What the address of Bali Zero please",
        "Is Antonello still working?",
        "Can you let me know please",
        "Thanks Alex",
    ]
    # 'Hi','What','Bali','Zero','Please','Can','Thanks','Is' must be filtered out.
    assert _distinct_names_in_texts(texts) == 2  # Antonello, Alex


def test_many_real_names_counts_high():
    texts = [
        "Lidia and Gerard need KITAS",
        "Jessica wants company setup",
        "Mikel and Jennifer paid",
        "Davide asked about tax",
    ]
    # Lidia, Gerard, Jessica, Mikel, Jennifer, Davide = 6 (KITAS/tax filtered)
    assert _distinct_names_in_texts(texts) == 6
