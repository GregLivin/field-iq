from pipeline.train_models import _reconcile_home_probability


def test_reconciler_moves_probability_toward_positive_margin():
    blended, score_prob = _reconcile_home_probability(0.50, 7.0, 13.0)
    assert score_prob > 0.50
    assert blended > 0.50
    assert blended < score_prob


def test_reconciler_moves_probability_toward_negative_margin():
    blended, score_prob = _reconcile_home_probability(0.50, -7.0, 13.0)
    assert score_prob < 0.50
    assert blended < 0.50
    assert blended > score_prob


def test_classifier_keeps_majority_weight():
    blended, _ = _reconcile_home_probability(0.80, 0.0, 13.0)
    assert blended > 0.65
