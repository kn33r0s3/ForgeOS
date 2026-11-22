"""dimag-relations v1 registry + unknown-type rejection.

The book (Part II section 07) names exactly 10 relations -- they ARE
the 10 base types. Only relation_type values in this registry are
accepted; unknown types are REJECTED at ingestion (book improvement
gate). Pure stdlib.
"""

RELATIONS_VERSION = "dimag-relations v1"

# Base relations: name -> id 0-9. Reverse forms are id + 10.
BASE_RELATIONS = {
    "CONTAINS": 0,
    "LEADS_TO": 1,
    "ADVANCES_TO": 2,
    "DEPENDS_ON": 3,
    "DERIVED_FROM": 4,
    "SUPPORTS": 5,
    "CONTRADICTS": 6,
    "SUPERSEDES": 7,
    "REVISITS": 8,
    "REFERENCES": 9,
}
BASE_RELATION_NAMES = tuple(BASE_RELATIONS.keys())


def reverse_relation_id(base_id):
    """Reverse form of a base relation id (0-9 -> 10-19)."""
    if not isinstance(base_id, int) or not 0 <= base_id < 10:
        raise ValueError("base relation id must be an integer in [0, 10)")
    return base_id + 10


# Gates-as-neurons aliases (docs/hami-gates-as-neurons.md section 2).
# NOTE: "feeds" is listed as the alias of BOTH LEADS_TO and ADVANCES_TO
# in design section 2.4. v1 resolves it to LEADS_TO (first-listed);
# every resolution is recorded in the example metadata
# (relation_alias_resolutions) so the choice stays visible. If the
# distinction ever matters, the schema version bumps and the mapping is
# re-decided with evidence -- never silently re-resolved.
ALIASES = {
    "depends_on": "DEPENDS_ON",
    "feeds": "LEADS_TO",
    "blocks": "CONTRADICTS",
}


class UnknownRelationTypeError(ValueError):
    """A relation_type outside dimag-relations v1. Raised at ingestion."""


def canonical_relation_name(name):
    """Resolve a relation_type to its canonical registry name.

    Accepts canonical names (CONTAINS, ...) and the gates-as-neurons
    aliases (depends_on, feeds, blocks). Anything else raises
    UnknownRelationTypeError. Returns (canonical_name, was_alias).
    """
    if not isinstance(name, str) or not name:
        raise UnknownRelationTypeError("relation_type must be a non-empty string")
    if name in BASE_RELATIONS:
        return name, False
    if name in ALIASES:
        return ALIASES[name], True
    raise UnknownRelationTypeError(
        "unknown relation_type %r: not in %s (known: %s)"
        % (name, RELATIONS_VERSION, ", ".join(BASE_RELATION_NAMES))
    )


def relation_id(name):
    """Base relation id (0-9) for a canonical name or alias."""
    canonical, _was_alias = canonical_relation_name(name)
    return BASE_RELATIONS[canonical]


def is_known_relation_type(name):
    """True iff the relation_type is in dimag-relations v1 (or an alias)."""
    try:
        canonical_relation_name(name)
        return True
    except UnknownRelationTypeError:
        return False
