"""Shared taxonomy helpers."""

from taxonomy.models import Domain

UNCATEGORIZED_DOMAIN_NAME = 'Uncategorized'


def get_or_create_uncategorized_domain() -> Domain:
    """Return the fallback domain used when fast import cannot resolve JSON domain."""
    domain, _created = Domain.objects.get_or_create(
        name=UNCATEGORIZED_DOMAIN_NAME,
        defaults={'description': 'Fallback domain for fast-imported units pending taxonomy review.'},
    )
    return domain
