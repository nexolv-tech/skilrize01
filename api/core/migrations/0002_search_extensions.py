"""
Enable the PostgreSQL extensions full-text search depends on.

Separated into its own migration, and depended on by every migration that
creates a trigram index, because `CREATE EXTENSION` needs elevated privileges
and is the one step most likely to fail on a locked-down managed database. When
it does, the failure should be this migration by name rather than a confusing
"operator class gin_trgm_ops does not exist" three migrations later.

`pg_trgm` powers the misspelling fallback in `core.search`: it is what lets
"photshop" still find "photoshop", which a stemmer alone cannot do.
"""

from django.contrib.postgres.operations import BtreeGinExtension, TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        TrigramExtension(),
        # Lets a GIN index cover a scalar column alongside a vector one, which
        # is what keeps the scope pre-filter and the text match on the same
        # index scan rather than two.
        BtreeGinExtension(),
    ]
