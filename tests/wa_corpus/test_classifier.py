from scripts.wa_corpus.classifier import CounterpartClassifier, Verdict

clf = CounterpartClassifier()


# --- 1. GROUP -------------------------------------------------------------

def test_group_chat_is_group():
    v = clf.classify(
        contact_type="contact", n_msgs=50, n_distinct_names=3, chat_type="group"
    )
    assert v.verdict is Verdict.GROUP
    assert v.loadable is False


def test_group_wins_even_if_in_crm():
    v = clf.classify(
        contact_type="contact", n_msgs=10, n_distinct_names=1,
        chat_type="group", in_crm=True,
    )
    assert v.verdict is Verdict.GROUP


# --- 2. INTERNAL (team beats client) -------------------------------------

def test_team_contact_type_is_internal():
    v = clf.classify(contact_type="team", n_msgs=275, n_distinct_names=30)
    assert v.verdict is Verdict.INTERNAL


def test_partner_contact_type_is_internal():
    assert clf.classify(contact_type="partner", n_msgs=10, n_distinct_names=1).verdict is Verdict.INTERNAL


def test_team_flag_is_internal_even_without_contact_type():
    # Surya's own outbound line: is_team_member=True, contact_type=None
    v = clf.classify(
        contact_type=None, n_msgs=37, n_distinct_names=2, is_team_member=True
    )
    assert v.verdict is Verdict.INTERNAL
    assert "team" in v.reason


def test_team_beats_client_when_both_true():
    # Lia: in CRM AND on the team roster -> still INTERNAL
    v = clf.classify(
        contact_type="team", n_msgs=108, n_distinct_names=5,
        is_team_member=True, in_crm=True,
    )
    assert v.verdict is Verdict.INTERNAL


# --- 3. MULTI_CLIENT ------------------------------------------------------

def test_high_volume_many_names_is_multi_client():
    v = clf.classify(contact_type="contact", n_msgs=275, n_distinct_names=30)
    assert v.verdict is Verdict.MULTI_CLIENT
    assert v.loadable is False


# --- 4. CLIENT (in CRM) ---------------------------------------------------

def test_in_crm_is_client():
    v = clf.classify(
        contact_type="contact", n_msgs=53, n_distinct_names=2, in_crm=True
    )
    assert v.verdict is Verdict.CLIENT
    assert v.loadable is True


def test_explicit_client_type_is_client():
    assert clf.classify(contact_type="client", n_msgs=40, n_distinct_names=1).verdict is Verdict.CLIENT


def test_client_visa_type_is_client():
    assert clf.classify(contact_type="client_visa", n_msgs=40, n_distinct_names=1).verdict is Verdict.CLIENT


# --- 5. PROSPECT (external, not in CRM) -----------------------------------

def test_external_not_in_crm_low_volume_is_prospect():
    v = clf.classify(contact_type="contact", n_msgs=20, n_distinct_names=1)
    assert v.verdict is Verdict.PROSPECT
    assert v.loadable is True


def test_none_contact_type_low_volume_external_is_prospect():
    assert clf.classify(contact_type=None, n_msgs=15, n_distinct_names=1).verdict is Verdict.PROSPECT


# --- 6. REVIEW ------------------------------------------------------------

def test_borderline_goes_to_review():
    # one stray high signal (volume high but few names) and not in CRM
    v = clf.classify(contact_type="contact", n_msgs=200, n_distinct_names=2)
    assert v.verdict is Verdict.REVIEW
    assert v.loadable is False
