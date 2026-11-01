"""Read Langscore translation tables without executing the plugin or game."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


CHINESE_LANGUAGES = ('zh-cn', 'zh-hans', 'zh-tw', 'zh-hant', 'zh')


def normalize(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n')


def language_id(text: str) -> str:
    return text.strip().casefold().replace('_', '-')


@dataclass
class LangscoreTables:
    folder: Path
    language: str
    # Each table has its own original strings. Never flatten differing map translations.
    entries: dict[tuple[str, str], tuple[str, str, str]] = field(default_factory=dict)
    used: set[tuple[str, str]] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    incomplete_files: list[str] = field(default_factory=list)
    _global: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    _line_endings: dict[tuple[str, str], list[tuple[str, str]]] = field(default_factory=dict)

    def build_index(self):
        self._global = defaultdict(list)
        self._line_endings = defaultdict(list)
        for key in self.entries:
            self._global[key[1]].append(key)
            self._line_endings[(key[0], key[1].rstrip('\n'))].append(key)

    def find(self, text: str, source: str = '') -> str | None:
        normalized = normalize(text)
        scope = Path(source.split(':', 1)[0]).stem.casefold() if source else ''
        scopes = [scope]
        if scope.startswith('map') and scope != 'mapinfos':
            # Runtime message conversion also falls back to shared event tables.
            scopes.extend(('troops', 'commonevents'))
        for candidate in scopes:
            key = (candidate, normalized)
            row = self.entries.get(key)
            if row and row[1].strip():
                self.used.add(key)
                return row[1]
            if row is None:
                keys = self._line_endings.get((candidate, normalized.rstrip('\n')), [])
                values = {self.entries[k][1] for k in keys if self.entries[k][1].strip()}
                if len(values) == 1:
                    self.used.update(keys)
                    return values.pop()
        if scope:
            return None
        keys = self._global.get(normalized, [])
        values = {self.entries[key][1] for key in keys if self.entries[key][1].strip()}
        if len(values) == 1:
            self.used.update(keys)
            return values.pop()
        return None

    def unused_entries(self):
        for key, (original, translated, filename) in self.entries.items():
            if key not in self.used:
                yield original, translated, filename


def load_langscore(root: Path) -> LangscoreTables | None:
    """Called only after confirming the Langscore plugin is enabled.

    Prefer the current translate directory over the older translates spelling,
    and simplified Chinese over traditional Chinese. Empty cells retain original text.
    """
    candidates = []
    for name in ('translate', 'translates'):
        folder = root / 'data' / name
        candidates.append(folder)
        if folder.is_dir():
            candidates.extend(sorted((p for p in folder.iterdir() if p.is_dir()),
                                     key=lambda p: CHINESE_LANGUAGES.index(language_id(p.name))
                                     if language_id(p.name) in CHINESE_LANGUAGES else len(CHINESE_LANGUAGES)))
    for folder in candidates:
        files = sorted(folder.glob('*.csv'))
        if not files:
            continue
        headers = {}
        header_errors = []
        for file in files:
            try:
                with file.open(encoding='utf-8-sig', newline='') as stream:
                    header = next(csv.reader(stream, strict=True), [])
                columns = [language_id(x) for x in header]
                if columns and columns[0] == 'original':
                    headers[file] = columns
                else:
                    header_errors.append(file)
            except (OSError, UnicodeError, csv.Error):
                header_errors.append(file)
        available = {x for columns in headers.values() for x in columns[1:]}
        language = next((lang for lang in CHINESE_LANGUAGES if lang in available), '')
        if not language:
            continue
        result = LangscoreTables(folder, language)

        def warn(file, message):
            relative = file.relative_to(root).as_posix()
            result.warnings.append(f'{relative} 译文未完整读取：{message}')
            if relative not in result.incomplete_files:
                result.incomplete_files.append(relative)

        for file in header_errors:
            warn(file, 'CSV 表头不可读或缺少 original 列。')
        for file, columns in headers.items():
            if language not in columns:
                continue
            index = columns.index(language)
            malformed = 0
            try:
                with file.open(encoding='utf-8-sig', newline='') as stream:
                    reader = csv.reader(stream, strict=True)
                    next(reader, None)
                    for row in reader:
                        if not row or not any(row):
                            continue
                        if len(row) != len(columns):
                            malformed += 1
                            continue
                        original, translated = normalize(row[0]), normalize(row[index])
                        if not original.strip():
                            continue
                        key = (file.stem.casefold(), original)
                        # Matches Langscore's Map.set behavior for duplicate CSV rows.
                        result.entries[key] = (original, translated, file.relative_to(root).as_posix())
                if malformed:
                    warn(file, f'{malformed} 行列数不符，已保留其他有效行。')
            except (OSError, UnicodeError, csv.Error) as error:
                warn(file, str(error))
        result.build_index()
        return result
    return None
