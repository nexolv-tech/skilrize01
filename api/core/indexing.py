"""
Keeping search vectors current.

Reindexing is done with a queryset `update()` rather than by assigning to the
instance, because `SearchVector` is a database expression: it has to be
evaluated by Postgres against the stored row. Assigning it in Python would
store the expression object, not the vector.

Vectors are rebuilt from the row itself, never patched incrementally. An
incremental update has to know which fields changed and reproduce exactly the
same weighting the full build uses — two implementations of one rule, which
drift, and the symptom is a listing that is unfindable by its own title.
"""

from __future__ import annotations

import logging

from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.db.models.fields import TextField
from django.db.models.functions import Cast, Coalesce

logger = logging.getLogger(__name__)


def _text(path: str):
    """A field as searchable text, with NULLs flattened to empty.

    `Coalesce` matters more than it looks: in Postgres a NULL anywhere in a
    concatenated vector makes the *whole* vector NULL, so one gig without a
    category would silently drop out of search entirely.
    """
    # `output_field` is required, not decorative: `Value("")` infers as a
    # CharField and the cast produces a TextField, which Django refuses to mix.
    return Coalesce(
        Cast(path, TextField()), Value("", output_field=TextField()), output_field=TextField()
    )


# Only *local* columns go into a vector. Postgres cannot resolve a joined field
# inside `UPDATE ... SET`, so `category__name` raises "Joined field references
# are not permitted in this query". Denormalising the category name onto the row
# purely to index it would be the wrong trade: category is already a first-class
# facet with its own filter and its own counts, so putting it in the free-text
# vector as well buys a second, fuzzier way to do something the facet already
# does exactly.


def gig_vector() -> SearchVector:
    from core.search import WEIGHT_BODY, WEIGHT_TAGS, WEIGHT_TITLE

    return (
        SearchVector(_text("title"), weight=WEIGHT_TITLE, config="english")
        + SearchVector(_text("tags"), weight=WEIGHT_TAGS, config="english")
        + SearchVector(_text("description"), weight=WEIGHT_BODY, config="english")
    )


def project_vector() -> SearchVector:
    from core.search import WEIGHT_BODY, WEIGHT_SKILLS, WEIGHT_TITLE

    return (
        SearchVector(_text("title"), weight=WEIGHT_TITLE, config="english")
        + SearchVector(_text("experience_level"), weight=WEIGHT_SKILLS, config="english")
        + SearchVector(_text("description"), weight=WEIGHT_BODY, config="english")
    )


def reindex_gig(gig_id: int) -> None:
    from gigs.models import Gig

    Gig.all_objects.filter(pk=gig_id).update(search_vector=gig_vector())


def reindex_project(project_id: int) -> None:
    from marketplace.models import Project

    Project.all_objects.filter(pk=project_id).update(search_vector=project_vector())


def reindex_all(batch: int = 1000) -> dict[str, int]:
    """Rebuild every vector. Safe to run at any time.

    Uses `all_objects` because indexing spans every surface — a campus gig
    still needs a vector, and the scoped manager would refuse to run at all
    outside a request.
    """
    from gigs.models import Gig
    from marketplace.models import Project

    counts = {}
    for label, model, vector in (
        ("gigs", Gig, gig_vector()),
        ("projects", Project, project_vector()),
    ):
        total = 0
        ids = list(model.all_objects.values_list("pk", flat=True))
        for start in range(0, len(ids), batch):
            chunk = ids[start : start + batch]
            total += model.all_objects.filter(pk__in=chunk).update(search_vector=vector)
        counts[label] = total

    logger.info("reindex_complete %s", counts)
    return counts
