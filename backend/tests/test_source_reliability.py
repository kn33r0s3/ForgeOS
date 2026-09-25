from app import models
from app.services import source_manager


def test_startup_does_not_assign_invented_source_ranks(db):
    source_manager.seed_default_sources(db)

    scores = {
        row.name: row.reliability_score
        for row in db.query(models.Source).all()
    }
    assert scores["arxiv"] == source_manager.UNMEASURED_RELIABILITY
    assert scores["reddit"] == source_manager.UNMEASURED_RELIABILITY
    assert scores["web"] == source_manager.UNMEASURED_RELIABILITY
    assert len(set(scores.values())) == 1


def test_unadjusted_invented_score_returns_to_baseline_and_adjusted_score_stays(db):
    github = db.query(models.Source).filter(models.Source.name == "github").one()
    github.reliability_score = source_manager.INVENTED_SEED_SCORES["github"]
    reddit = db.query(models.Source).filter(models.Source.name == "reddit").one()
    reddit.reliability_score = 61.5
    db.commit()

    source_manager.seed_default_sources(db)
    db.refresh(github)
    db.refresh(reddit)

    assert github.reliability_score == source_manager.UNMEASURED_RELIABILITY
    assert reddit.reliability_score == 61.5
