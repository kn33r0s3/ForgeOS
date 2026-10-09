"""
CURIOSITY ENGINE
=================

Forge's answer to "what should I investigate next to understand
reality better?" — instead of collecting information blindly, it looks
at what it already knows, finds the weak spots, and turns those into
concrete research questions.

Eight kinds of weak spots (per spec):

  1. Low-confidence beliefs   -> a hypothesis Forge isn't sure about yet
  2. Unexplored patterns      -> repeated signals with no belief formed
  3. Contradicting evidence    -> two patterns that share a topic but
                                   pull in opposite directions
  4. Unstable beliefs           -> a belief whose confidence keeps
                                    swinging or is accumulating
                                    contradictions, REGARDLESS of its
                                    current confidence_score — a belief
                                    can be moderately confident right
                                    now and still be worth investigating
                                    if it's not settling (v0.8, see
                                    belief_stability.py)
  5. Untested important beliefs
     & contradictory causal knowledge -> a belief that matters (goal-
                                          relevant) but has never been
                                          causally tested, OR an action
                                          whose repeated outcomes can't
                                          agree with each other (v0.9,
                                          see causal_engine.py)
  6. Low-confidence strategies  -> a candidate Strategy whose evidence
                                     doesn't yet support recommending it
                                     confidently — this is what stops
                                     Forge from pretending certainty
                                     about what to do next (v1.0, see
                                     strategy_engine.py)
  7. Unvalidated opportunities   -> an Opportunity with a decent
                                      money_score but zero revenue
                                      evidence — "looks promising on
                                      paper" isn't the same as "worth
                                      pursuing," and this is what turns
                                      that gap into a concrete research
                                      question instead of quiet
                                      overconfidence (v1.2, see
                                      money_engine.py)
  8. Ungrounded opportunities     -> an Opportunity with an inferred
                                       monetization model but no linked
                                       RevenueSource — Forge has a
                                       plausible-sounding model, not a
                                       verified real payout mechanism,
                                       and this surfaces that gap as
                                       "which actual platform/program
                                       would pay for this" (v1.3, see
                                       money_engine.py's Revenue Sources)

Question generation is template-based (mad-libs style, keyword-driven)
— deliberately not an LLM call, so this stays free and instant. The
templates can be swapped for ai_engine.py calls later without changing
the public methods.

Priority is boosted (not replaced) by goal relevance in two independent
ways — see goal_engine.py: TEXTUAL (keyword overlap with a goal's
wording, applied to every question) and STRUCTURAL (the underlying
Pattern already has a real Opportunity serving an active goal —
stronger evidence than wording alone, applied only where a Pattern is
directly available). With no goals defined, both boosts are 0.0 and
this behaves exactly as it did before Goal Engine existed.
"""

from sqlalchemy.orm import Session

import re
from typing import Optional

from app import models
from app.services import goal_engine, belief_stability, causal_engine, money_engine
from app.services.pattern_engine import tokenize

# Standing questions for the world Forge is responsible for. Each one asks
# for current public evidence. None of them states a price, a valuation,
# or a fact. The cycle stores a question once; collectors may later attach
# observations. Those observations are not publication and not verification.
WORLD_RESEARCH_AGENDA = (
    "What current public evidence describes jobs and unmet demand for work in Nepal?",
    "What current public evidence describes local service supply gaps in Nepal?",
    "What current public evidence describes goods, trades, and stated prices people in Nepal actually post?",
    "What current public evidence describes residential and commercial real estate conditions in Nepal?",
    "What current public evidence describes supply and movement in gold, oil, and agricultural commodities?",
    "What current public evidence describes fixed-income, government-bond, and cash-market conditions relevant to Nepal?",
    "What current public evidence describes equity market conditions relevant to Nepal and the region?",
    "What current public evidence describes derivatives markets and their risks relevant to Nepal and the region?",
    "What current public evidence describes currency moves of NPR against USD, INR, and EUR?",
    "What current public evidence describes infrastructure, energy, and data-center investment affecting Nepal?",
    "What current public evidence describes private credit, startup funding, and small-business capital in Nepal?",
    "What current public evidence describes hedge-fund situations and documented exposure relevant to Nepal and the region?",
    "What current public evidence describes cryptocurrency use and risk relevant to Nepal?",
    "What current public evidence describes insurance, reinsurance, remittances, and household financial protection in Nepal?",
)

LOW_CONFIDENCE_THRESHOLD = 50.0
LOW_STRATEGY_CONFIDENCE_THRESHOLD = 50.0
UNVALIDATED_OPPORTUNITY_MIN_SCORE = 40.0  # only worth a research question if it's at least plausible on paper

POSITIVE_WORDS = {"want", "need", "adopt", "love", "prefer", "willing"}
NEGATIVE_WORDS = {"avoid", "refuse", "distrust", "reject", "against", "skeptical"}


class CuriosityEngine:
    def __init__(self, db: Session):
        self.db = db

    # --- finding weak spots -------------------------------------------------

    def find_low_confidence_beliefs(self, threshold: float = LOW_CONFIDENCE_THRESHOLD) -> list[models.Belief]:
        from app.services.belief_engine import is_presentable_belief
        return [
            belief
            for belief in self.db.query(models.Belief).filter(models.Belief.confidence_score < threshold).all()
            if is_presentable_belief(belief)
        ]

    def find_unexplored_patterns(self) -> list[models.Pattern]:
        """Patterns Forge has detected but never turned into a belief.

        Skips patterns classified as [BIBLIOGRAPHIC BACKGROUND] — these are
        retained as background observations but do not generate commercial
        questions without a real-world problem behind them.

        Further requires commercial qualification: the pattern's supporting
        signals must predominantly indicate real-world problems or demand
        (signal_type in 'problem'/'demand'), not mere observations. A missing
        grounding link remains missing — we do not invent problems to make
        patterns qualify."""
        from app.services.belief_engine import is_presentable_belief
        patterns = self.db.query(models.Pattern).all()
        beliefs = [belief for belief in self.db.query(models.Belief).all() if is_presentable_belief(belief)]
        belief_text = " ".join(b.statement.lower() for b in beliefs)
        belief_tokens = set()
        for b in beliefs:
            belief_tokens |= tokenize(b.statement)

        unexplored = []
        for pattern in patterns:
            # Skip bibliographic background observations — they lack the
            # real-world problem context needed for commercial questions.
            if pattern.description and "[BIBLIOGRAPHIC BACKGROUND]" in pattern.description:
                continue
            # Require commercial qualification: pattern must be grounded in
            # real-world problems/demand, not just observations.
            if not self._is_commercially_qualified(pattern):
                continue
            top_keyword = pattern.title.replace("Recurring theme:", "").split(",")[0].strip().lower()
            if not top_keyword:
                continue
            # Keyword matching is word-boundary-aware, not a raw
            # substring check: a belief mentioning "taxes" must not
            # mark a "tax"-keyword pattern as explored, and "ai"
            # must not match inside "said". tokenize() strips
            # stopwords and sub-3-letter words, so short keywords
            # (or all-stopword keywords) fall back to an explicit
            # word-boundary regex on the raw keyword.
            keyword_tokens = tokenize(top_keyword)
            if keyword_tokens:
                explored = keyword_tokens <= belief_tokens
            else:
                explored = re.search(r"\b" + re.escape(top_keyword) + r"\b", belief_text) is not None
            if not explored:
                unexplored.append(pattern)
        return unexplored

    def _is_commercially_qualified(self, pattern: models.Pattern) -> bool:
        """Check if a pattern is grounded enough for commercial question generation.

        A pattern qualifies only if the majority of its supporting signals
        indicate real-world problems or demand (signal_type='problem' or
        'demand'), not mere observations. This uses the existing Signal
        classification — we do not invent grounding.

        The five criteria from the relevance gate map to existing structures:
        1. Hami unknown → the ResearchQuestion created from this pattern
        2. Geography/population → implied by problem/demand signals (real-world context)
        3. Evidence requirement → the question text describes the uncertainty
        4. Decision consequence → linkable via Claim.decision_id (future)
        5. Next test → linkable via Claim.experiment_id (future)

        A missing link remains missing. Patterns without problem/demand grounding
        are retained as background observations but do not generate commercial
        questions.
        """
        if not pattern.origin_signal_ids:
            return False

        try:
            signal_ids = [int(sid.strip()) for sid in pattern.origin_signal_ids.split(",") if sid.strip()]
        except (ValueError, AttributeError):
            return False

        if not signal_ids:
            return False

        signals = self.db.query(models.Signal).filter(models.Signal.id.in_(signal_ids)).all()
        if not signals:
            return False

        # Count signals indicating real-world problems or demand
        grounded = sum(1 for s in signals if (s.signal_type or "").lower() in ("problem", "demand"))

        # Require majority grounding
        return grounded >= len(signals) / 2

    def find_contradictions(self) -> list[tuple[models.Pattern, models.Pattern]]:
        """Naive contradiction detection: two patterns that share a
        keyword but lean opposite directions on sentiment words (one
        "wants/adopts", the other "avoids/refuses")."""
        patterns = self.db.query(models.Pattern).all()
        contradictions = []
        for i, a in enumerate(patterns):
            a_kw = tokenize(a.description)
            a_positive = bool(POSITIVE_WORDS & a_kw)
            a_negative = bool(NEGATIVE_WORDS & a_kw)
            for b in patterns[i + 1:]:
                b_kw = tokenize(b.description)
                if not (a_kw & b_kw):
                    continue
                b_positive = bool(POSITIVE_WORDS & b_kw)
                b_negative = bool(NEGATIVE_WORDS & b_kw)
                if (a_positive and b_negative) or (a_negative and b_positive):
                    contradictions.append((a, b))
        return contradictions

    def find_unstable_beliefs(self) -> list[models.Belief]:
        """Beliefs whose STABILITY is low, independent of their current
        confidence_score — a belief can be moderately or even highly
        confident right now while still swinging around or picking up
        contradictions, which find_low_confidence_beliefs() alone would
        never surface (it only looks at the current number)."""
        from app.services.belief_engine import is_presentable_belief
        unstable = []
        for belief in self.db.query(models.Belief).all():
            if not is_presentable_belief(belief):
                continue
            stability = belief_stability.get_belief_stability(self.db, belief.id)["stability_score"]
            if stability < belief_stability.UNSTABLE_THRESHOLD:
                unstable.append(belief)
        return unstable

    def find_untested_important_beliefs(self) -> list[models.Belief]:
        """Beliefs that matter (some goal relevance, structural or
        textual) but have never been causally tested — no
        CausalKnowledge row exists linking to them yet. Covers both
        "high-impact unknown causes" and "untested actions" from the
        spec: a belief Forge cares about but has no track record of
        actually acting on."""
        from app.services.belief_engine import is_presentable_belief
        untested = []
        for belief in self.db.query(models.Belief).all():
            if not is_presentable_belief(belief):
                continue
            importance = goal_engine.belief_goal_relevance(self.db, belief)
            if importance <= 0:
                continue
            has_causal_knowledge = (
                self.db.query(models.CausalKnowledge)
                .filter(models.CausalKnowledge.belief_id == belief.id)
                .first()
            )
            if not has_causal_knowledge:
                untested.append(belief)
        return untested

    def find_contradictory_causal_knowledge(self) -> list[models.CausalKnowledge]:
        """Causal knowledge with mixed outcomes — enough supporting
        experiments to have a real track record (2+), but confidence
        sitting in the contested middle rather than settling toward
        clear success or clear failure. Verified against
        causal_engine.py's own math: alternating success/failure across
        four experiments lands at 40.0, squarely inside this range."""
        contradictory = []
        for causal in self.db.query(models.CausalKnowledge).all():
            support_count = (
                len(causal.supporting_experiment_ids.split(","))
                if causal.supporting_experiment_ids
                else 0
            )
            if support_count >= 2 and 35.0 <= causal.confidence <= 65.0:
                contradictory.append(causal)
        return contradictory

    def find_low_confidence_strategies(self) -> list[models.Strategy]:
        """Candidate strategies (not superseded) whose confidence is
        low — Forge shouldn't pretend certainty about what to do next
        toward a goal when the evidence doesn't actually support it.
        This is what turns "strategy confidence is low because only
        one experiment supports this" into a research opportunity
        instead of quiet overconfidence (v1.0 spec, item 6)."""
        return (
            self.db.query(models.Strategy)
            .filter(
                models.Strategy.status == "candidate",
                models.Strategy.confidence < LOW_STRATEGY_CONFIDENCE_THRESHOLD,
            )
            .all()
        )

    def find_unvalidated_opportunities(self) -> list[tuple[models.Opportunity, float]]:
        """Opportunities that look plausible on paper (money_score
        above a floor — not every idea deserves a question) but have
        zero revenue evidence — revenue_confidence still at its
        untouched starting value of 0.0. "Looks promising" and "worth
        pursuing" are different claims; this is what keeps Forge from
        treating the first as the second (v1.2 spec).

        Returns (opportunity, money_score) pairs so callers don't have
        to re-run money_engine.score_opportunity() just to compute a
        priority — one scoring pass per opportunity, not two."""
        unvalidated = []
        for opportunity in self.db.query(models.Opportunity).filter(models.Opportunity.revenue_confidence == 0.0).all():
            breakdown = money_engine.score_opportunity(self.db, opportunity)
            if breakdown["money_score"] >= UNVALIDATED_OPPORTUNITY_MIN_SCORE:
                unvalidated.append((opportunity, breakdown["money_score"]))
        return unvalidated

    def find_ungrounded_opportunities(self) -> list[models.Opportunity]:
        """Opportunities with an inferred monetization_model (Forge has
        a guess at HOW this could make money) but no linked
        RevenueSource (Forge hasn't tied that guess to any real,
        verifiable platform or program). A plausible-sounding model
        isn't the same as a known payout mechanism (v1.3 spec)."""
        return (
            self.db.query(models.Opportunity)
            .filter(
                models.Opportunity.monetization_model.isnot(None),
                models.Opportunity.monetization_model != "unknown",
                models.Opportunity.revenue_source_id.is_(None),
            )
            .all()
        )

    # --- generating questions -----------------------------------------------

    def generate_questions_for_pattern(self, pattern: models.Pattern) -> list[str]:
        topic = pattern.title.replace("Recurring theme:", "").strip()
        return [
            f"What specific problems do people mean when they mention {topic}?",
            f"Why might people avoid solutions related to {topic}?",
            f"Which audience would pay the most to solve {topic}?",
        ]

    def generate_questions_for_belief(self, belief: models.Belief) -> list[str]:
        return [
            f'What evidence would make "{belief.statement}" more certain?',
            f'What evidence would disprove "{belief.statement}"?',
        ]

    def generate_questions_for_contradiction(self, a: models.Pattern, b: models.Pattern) -> list[str]:
        topic_a = a.title.replace("Recurring theme:", "").strip()
        topic_b = b.title.replace("Recurring theme:", "").strip()
        return [f"Why do signals about \"{topic_a}\" and \"{topic_b}\" seem to disagree?"]

    def generate_questions_for_instability(self, belief: models.Belief) -> list[str]:
        return [
            f'Why does confidence in "{belief.statement}" keep changing?',
            f'What would settle whether "{belief.statement}" is actually true?',
        ]

    def generate_questions_for_untested_belief(self, belief: models.Belief) -> list[str]:
        return [
            f'What action, if tested, would validate or disprove "{belief.statement}"?',
        ]

    def generate_questions_for_contradictory_causal(self, causal: models.CausalKnowledge) -> list[str]:
        return [
            f'Why does "{causal.action}" produce inconsistent results under "{causal.condition}"?',
        ]

    def generate_questions_for_uncertain_strategy(self, strategy: models.Strategy) -> list[str]:
        return [
            f'What additional evidence would increase confidence in the strategy '
            f'"{strategy.title}"? Currently: {strategy.rationale}',
        ]

    def generate_questions_for_unvalidated_opportunity(self, opportunity: models.Opportunity) -> list[str]:
        return [
            f'What revenue experiment would validate willingness to pay for '
            f'"{opportunity.offer or opportunity.solution}"?',
        ]

    def generate_questions_for_ungrounded_opportunity(self, opportunity: models.Opportunity) -> list[str]:
        return [
            f'Which real platform or program would actually pay for '
            f'"{opportunity.offer or opportunity.solution}" via a {opportunity.monetization_model} model?',
        ]

    # --- storing + running the full scan ------------------------------------

    def _store_question(
        self, text: str, priority: float, pattern_id: Optional[int] = None, belief_id: Optional[int] = None
    ) -> models.ResearchQuestion:
        existing = (
            self.db.query(models.ResearchQuestion)
            .filter(models.ResearchQuestion.question == text)
            .first()
        )
        if existing:
            return existing

        # Goal Engine integration: a question that overlaps an active
        # goal's keywords gets a modest priority boost. No active goals
        # (or a fresh install with none created) -> boost is 0.0 and
        # this behaves exactly as before Goal Engine existed.
        boosted_priority = round(min(100.0, priority + goal_engine.goal_relevance_boost(self.db, text)), 1)

        question = models.ResearchQuestion(
            question=text,
            priority_score=boosted_priority,
            status="open",
            source_pattern_id=pattern_id,
            source_belief_id=belief_id,
        )
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return question

    def open_world_research(self) -> list[models.ResearchQuestion]:
        """Open any standing world question that is not already stored.

        Idempotent. A second call in a later cycle adds nothing. This does
        not create beliefs, opportunities, providers, or prices.
        """
        opened: list[models.ResearchQuestion] = []
        for text in WORLD_RESEARCH_AGENDA:
            exists = (
                self.db.query(models.ResearchQuestion)
                .filter(models.ResearchQuestion.question == text)
                .first()
            )
            if exists:
                continue
            opened.append(self._store_question(text, priority=70.0))
        return opened

    def run_curiosity_scan(self) -> list[models.ResearchQuestion]:
        """Full scan: find every weak spot, generate questions for
        each, store new ones (existing identical questions are
        returned as-is, not duplicated). Returns every question
        touched this scan.

        Priority gets two independent goal-relevance boosts where
        applicable: TEXTUAL (keyword overlap with a goal's wording,
        applied uniformly to every question inside _store_question)
        and, where a Pattern is directly available, STRUCTURAL (a real
        pattern -> Opportunity -> goal link — stronger evidence than
        wording alone). The two are added at different points
        specifically so the same textual signal never gets counted
        twice."""
        created: list[models.ResearchQuestion] = []
        created.extend(self.open_world_research())

        for belief in self.find_low_confidence_beliefs():
            structural_boost = goal_engine.structural_goal_relevance(self.db, belief.pattern_id)
            for text in self.generate_questions_for_belief(belief):
                created.append(
                    self._store_question(text, priority=75.0 + structural_boost, belief_id=belief.id)
                )

        for pattern in self.find_unexplored_patterns():
            structural_boost = goal_engine.structural_goal_relevance(self.db, pattern.id)
            for text in self.generate_questions_for_pattern(pattern):
                created.append(
                    self._store_question(text, priority=60.0 + structural_boost, pattern_id=pattern.id)
                )

        for pattern_a, pattern_b in self.find_contradictions():
            structural_boost = goal_engine.structural_goal_relevance(self.db, pattern_a.id)
            for text in self.generate_questions_for_contradiction(pattern_a, pattern_b):
                created.append(
                    self._store_question(text, priority=85.0 + structural_boost, pattern_id=pattern_a.id)
                )

        # Unstable beliefs get their OWN boost (instability_boost),
        # not the structural goal boost the other three loops use —
        # instability_boost already blends stability with goal
        # relevance internally (see belief_stability.py), so adding
        # structural_goal_relevance here too would double-count the
        # same importance signal.
        for belief in self.find_unstable_beliefs():
            boost = belief_stability.instability_boost(self.db, belief)
            for text in self.generate_questions_for_instability(belief):
                created.append(self._store_question(text, priority=65.0 + boost, belief_id=belief.id))

        # Untested-but-important beliefs: priority scales directly with
        # how goal-relevant the belief already is — a belief nobody
        # cares about yet doesn't need urgent causal testing.
        for belief in self.find_untested_important_beliefs():
            importance = goal_engine.belief_goal_relevance(self.db, belief)
            for text in self.generate_questions_for_untested_belief(belief):
                created.append(
                    self._store_question(text, priority=70.0 + min(20.0, importance * 0.3), belief_id=belief.id)
                )

        # Contradictory causal knowledge: high base priority (resolving
        # conflicting evidence about what actually works is inherently
        # important), boosted further if the action is tied to an
        # active goal.
        for causal in self.find_contradictory_causal_knowledge():
            boost = causal_engine.causal_goal_boost(self.db, causal)
            for text in self.generate_questions_for_contradictory_causal(causal):
                created.append(
                    self._store_question(text, priority=80.0 + boost, belief_id=causal.belief_id)
                )

        # Low-confidence strategies: priority scales inversely with
        # confidence — the LESS confident a candidate strategy is, the
        # more it needs investigation before Forge could recommend it.
        # Linked back to the strategy's supporting belief (if any) for
        # traceability, reusing ResearchQuestion's existing
        # source_belief_id column rather than adding a new one.
        for strategy in self.find_low_confidence_strategies():
            linked_belief_id = None
            if strategy.supporting_belief_ids:
                first_id = strategy.supporting_belief_ids.split(",")[0].strip()
                if first_id.isdigit():
                    linked_belief_id = int(first_id)
            priority = round(min(95.0, 50.0 + (100.0 - strategy.confidence) * 0.45), 1)
            for text in self.generate_questions_for_uncertain_strategy(strategy):
                created.append(self._store_question(text, priority=priority, belief_id=linked_belief_id))

        # Unvalidated opportunities: priority scales with how promising
        # the opportunity looks on paper (its own money_score) — a
        # higher-scoring unvalidated opportunity is more urgent to test
        # than a marginal one. Linked back via the opportunity's
        # pattern_id, reusing ResearchQuestion's existing
        # source_pattern_id column rather than adding a new one.
        for opportunity, money_score in self.find_unvalidated_opportunities():
            priority = round(min(95.0, 50.0 + money_score * 0.4), 1)
            for text in self.generate_questions_for_unvalidated_opportunity(opportunity):
                created.append(
                    self._store_question(text, priority=priority, pattern_id=opportunity.pattern_id)
                )

        # Ungrounded opportunities: fixed, modest priority — this is a
        # lower-urgency gap than "untested" (a model with no real
        # source is still a plausible starting hypothesis, not nothing).
        for opportunity in self.find_ungrounded_opportunities():
            for text in self.generate_questions_for_ungrounded_opportunity(opportunity):
                created.append(
                    self._store_question(text, priority=55.0, pattern_id=opportunity.pattern_id)
                )

        return created
