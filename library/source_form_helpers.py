"""Parse author/tag text inputs for Source forms."""

import re

from taxonomy.models import Tag

from .models import Author


def parse_author_names(text: str) -> list[str]:
    if not text or not str(text).strip():
        return []
    parts = re.split(r'[;|]', str(text))
    seen = set()
    names = []
    for part in parts:
        name = part.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name[:255])
    return names


def parse_tag_names(text: str) -> list[str]:
    if not text or not str(text).strip():
        return []
    seen = set()
    names = []
    for part in str(text).split(','):
        name = part.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name[:100])
    return names


def authors_to_text(source) -> str:
    if not source or not source.pk:
        return ''
    return '; '.join(source.authors.order_by('name').values_list('name', flat=True))


def tags_to_text(source) -> str:
    if not source or not source.pk:
        return ''
    return ', '.join(source.tags.order_by('name').values_list('name', flat=True))


def assign_authors_from_text(source, text: str) -> None:
    names = parse_author_names(text)
    authors = []
    for name in names:
        author, _ = Author.objects.get_or_create(
            name=name,
            defaults={'organization': ''},
        )
        authors.append(author)
    source.authors.set(authors)


def assign_tags_from_text(source, text: str) -> None:
    names = parse_tag_names(text)
    tags = []
    for name in names:
        tag, _ = Tag.objects.get_or_create(name=name)
        tags.append(tag)
    source.tags.set(tags)
