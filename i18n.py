"""Request-scoped localization and lossless report templates.

Only explicit developer-authored templates are translated. Formatting arguments
(such as player or planet names) remain literal. Reports store template trees so
requests and background simulation cannot lock their text to another language.
"""
from __future__ import annotations

import json
from string import Formatter
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

SUPPORTED = ('en', 'pl', 'de', 'es', 'fr')
# Direct simulation calls preserve the pre-localization Polish API. Every HTTP
# request overrides this with negotiated language, defaulting to English.
_language = ContextVar('alien_colonies_language', default='pl')
_request_catalogs = ContextVar('alien_colonies_catalogs', default=None)


def negotiate_language(value):
    """Resolve BCP-47 language/region tags and Accept-Language quality weights."""
    candidates = []
    for index, part in enumerate(str(value or '').split(',')):
        pieces = part.strip().lower().replace('_', '-').split(';')
        tag = pieces[0].split('-')[0]
        quality = 1.0
        for option in pieces[1:]:
            if option.strip().startswith('q='):
                try:
                    quality = float(option.strip()[2:])
                except ValueError:
                    quality = 0.0
        if tag in SUPPORTED and 0 < quality <= 1:
            candidates.append((-quality, index, tag))
    return min(candidates)[2] if candidates else 'en'


@contextmanager
def language_scope(value='en'):
    token = _language.set(negotiate_language(value))
    catalogs_token = _request_catalogs.set({})
    try:
        yield _language.get()
    finally:
        _language.reset(token)
        _request_catalogs.reset(catalogs_token)


@lru_cache(maxsize=10)
def _catalog_file(filename, stamp):
    try:
        value = json.loads(Path(filename).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _catalog(language):
    scoped = _request_catalogs.get()
    if scoped is not None and language in scoped:
        return scoped[language]
    base = Path(__file__).resolve().parent
    result = {}
    # Support both the original localization/ folder and a flat Railway/GitHub
    # layout where language JSON files live next to i18n.py. The flat layout is
    # intentionally supported because GitHub web uploads can omit subfolders.
    for directory in (base, base.parent / 'localization', base / 'localization'):
        for filename in ('server_' + language + '.json', language + '.json'):
            path = directory / filename
            try:
                result.update(_catalog_file(str(path), path.stat().st_mtime_ns))
            except OSError:
                pass
    if scoped is not None:
        scoped[language] = result
    return result


def _translation(source, language):
    if language == 'pl':
        return source
    return _catalog(language).get(source, _catalog('en').get(source, source))


def format_number(value, spec='g', language=None):
    text = format(value, spec)
    if (language or _language.get()) in ('pl', 'de', 'es', 'fr'):
        text = text.replace('.', ',')
    return text


def store_text(value):
    """A plain JSON value, never a locale-dependent string subclass in storage."""
    return value.template if isinstance(value, LocalizedText) else value


class _NumberFormatter(Formatter):
    def __init__(self, language):
        self.language = language

    def format_field(self, value, spec):
        result = super().format_field(value, spec)
        if isinstance(value, float) and self.language in ("pl", "de", "es", "fr"):
            result = result.replace(".", ",")
        return result


def render_text(value, language=None):
    language = language or _language.get()
    if isinstance(value, LocalizedText):
        value = value.template
    if not isinstance(value, dict) or value.get('_l10n') != 1:
        return value
    if 'parts' in value:
        return str(value.get('separator', '')).join(str(render_text(part, language)) for part in value['parts'])
    source = value.get('source', '')
    template = _translation(source, language)
    args = [render_text(arg, language) for arg in value.get('args', [])]
    kwargs = {key: render_text(arg, language) for key, arg in value.get('kwargs', {}).items()}
    if not args and not kwargs:
        return template
    try:
        return _NumberFormatter(language).format(template, *args, **kwargs)
    except (IndexError, KeyError, ValueError):
        # A malformed catalog cannot break gameplay or discard report content.
        return _NumberFormatter(language).format(source, *args, **kwargs)


class LocalizedText(str):
    def __new__(cls, template):
        instance = str.__new__(cls, str(render_text(template)))
        instance.template = template
        return instance

    def __add__(self, other):
        return join_text('', (self, other))

    def __radd__(self, other):
        return join_text('', (other, self))

    def format(self, *args, **kwargs):
        return LocalizedText({**self.template, 'args': [store_text(arg) for arg in args],
                              'kwargs': {key: store_text(value) for key, value in kwargs.items()}})

    def __reduce__(self):
        return (LocalizedText, (self.template,))


def t(source):
    if isinstance(source, LocalizedText):
        return LocalizedText(source.template)
    return LocalizedText({'_l10n': 1, 'source': source})


def join_text(separator, parts):
    return LocalizedText({'_l10n': 1, 'separator': separator,
                          'parts': [store_text(part) for part in parts]})


def public_report(report):
    result = dict(report)
    translated = result.pop('i18n', {})
    for key in ('title', 'text'):
        if key in translated:
            result[key] = render_text(translated[key])
        elif key == 'title':
            # Legacy report bodies contain embedded user names: keep them intact.
            # Their fixed titles can still be translated without guessing names.
            result[key] = t(result.get(key, ''))
    return result
