from scripts.wa_corpus.classifier import CounterpartClassifier, Verdict

clf = CounterpartClassifier()


def test_team_contact_type_is_internal():
    v = clf.classify(contact_type="team", n_msgs=275, n_distinct_names=30)
    assert v.verdict is Verdict.INTERNAL
    assert "team" in v.reason


def test_partner_and_group_excluded():
    assert clf.classify(contact_type="partner", n_msgs=10, n_distinct_names=1).verdict is Verdict.INTERNAL
    assert clf.classify(contact_type="group", n_msgs=10, n_distinct_names=1).verdict is Verdict.INTERNAL


def test_explicit_client_type_is_client():
    v = clf.classify(contact_type="client", n_msgs=40, n_distinct_names=1)
    assert v.verdict is Verdict.CLIENT


def test_client_visa_type_is_client():
    assert clf.classify(contact_type="client_visa", n_msgs=40, n_distinct_names=1).verdict is Verdict.CLIENT


def test_unclassified_low_volume_is_client():
    # 'contact' default + low volume + one name -> treat as 1-a-1 client
    v = clf.classify(contact_type="contact", n_msgs=53, n_distinct_names=1)
    assert v.verdict is Verdict.CLIENT


def test_unclassified_high_volume_many_names_is_multi_client():
    # the +628563785797-style operational channel (but NOT marked team)
    v = clf.classify(contact_type="contact", n_msgs=275, n_distinct_names=30)
    assert v.verdict is Verdict.MULTI_CLIENT


def test_none_contact_type_low_volume_is_client():
    assert clf.classify(contact_type=None, n_msgs=20, n_distinct_names=1).verdict is Verdict.CLIENT


def test_borderline_goes_to_review():
    # high volume but few names, or many names but low volume -> needs a human
    v = clf.classify(contact_type="contact", n_msgs=200, n_distinct_names=2)
    assert v.verdict is Verdict.REVIEW
