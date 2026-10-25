"""Data-only Ruby Marshal 4.8 reader for RPG Maker VX Ace.

Reference: https://docs.ruby-lang.org/en/2.7.0/marshal_rdoc.html
Never calls Ruby, resolves classes, executes scripts or invokes _load hooks.
User-defined binary payloads (Table, Color, Tone) are skipped as opaque data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(eq=False)
class RubyString:
    data: bytes
    encoding: str = 'utf-8'

    def text(self):
        aliases = {'ASCII-8BIT': 'utf-8', 'Windows-31J': 'cp932', 'UTF-8': 'utf-8'}
        encoding = aliases.get(self.encoding, self.encoding)
        for name in dict.fromkeys([encoding, 'utf-8', 'cp932', 'gb18030']):
            try:
                return self.data.decode(name)
            except (UnicodeDecodeError, LookupError):
                pass
        return self.data.decode('utf-8', errors='replace')


class MarshalReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.symbols = []
        self.objects = []

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError(f'Ruby 数据长度异常，位置 {self.pos}')
        value = self.data[self.pos:self.pos+count]
        self.pos += count
        return value

    def number(self):
        n = int.from_bytes(self.take(1), 'little', signed=True)
        if n == 0:
            return 0
        if n > 4:
            return n - 5
        if n < -4:
            return n + 5
        raw = int.from_bytes(self.take(abs(n)), 'little')
        return raw if n > 0 else raw - (1 << (-8*n))

    def length(self):
        count = self.number()
        if count < 0 or count > len(self.data) - self.pos:
            raise ValueError(f'Ruby 容器长度异常，位置 {self.pos}')
        return count

    def bytes(self):
        return self.take(self.length())

    def register(self, value):
        self.objects.append(value)
        return value

    def read(self, depth=0):
        if depth > 250:
            raise ValueError('Ruby 数据嵌套过深')
        tag = self.take(1)
        nested = lambda: self.read(depth+1)
        if tag == b'0':
            return None
        if tag in (b'T', b'F'):
            return tag == b'T'
        if tag == b'i':
            return self.number()
        if tag == b':':
            value = self.bytes().decode('utf-8', errors='replace')
            self.symbols.append(value)
            return value
        if tag in (b';', b'@'):
            table = self.symbols if tag == b';' else self.objects
            index = self.number()
            if index < 0 or index >= len(table):
                raise ValueError(f'Ruby 引用越界，位置 {self.pos}')
            return table[index]
        if tag == b'"':
            return self.register(RubyString(self.bytes()))
        if tag == b'[':
            result = self.register([])
            count = self.length()
            for _ in range(count):
                result.append(nested())
            return result
        if tag in (b'{', b'}'):
            result = self.register({})
            count = self.length()
            for _ in range(count):
                key = nested()
                result[key] = nested()
            if tag == b'}':
                nested()  # Hash default value is not visible game text.
            return result
        if tag in (b'o', b'S'):
            klass = nested()
            result = self.register({'__ruby_class__': klass})
            count = self.length()
            for _ in range(count):
                key = nested()
                result[key] = nested()
            return result
        if tag == b'I':
            obj = nested()
            count = self.length()
            for _ in range(count):
                key, value = nested(), nested()
                if isinstance(obj, RubyString):
                    if key == 'E':
                        obj.encoding = 'utf-8' if value else 'ascii'
                    elif key == 'encoding':
                        obj.encoding = value.text() if isinstance(value, RubyString) else str(value)
                elif isinstance(obj, dict):
                    obj[key] = value
            return obj
        if tag == b'u':
            klass = nested()
            self.bytes()  # No hooks, and binary tile arrays are irrelevant to text extraction.
            return self.register({'__opaque__': klass})
        if tag in (b'U', b'd'):
            klass = nested()
            result = self.register({'__ruby_class__': klass})
            result['data'] = nested()
            return result
        if tag in (b'C', b'e'):
            nested()  # Class/module symbol; do not resolve it.
            return nested()
        if tag in (b'c', b'm', b'M'):
            return self.register({'__opaque__': self.bytes().decode('utf-8', errors='replace')})
        if tag == b'/':
            value = self.register(RubyString(self.bytes()))
            self.take(1)
            return value
        if tag == b'f':
            return self.register(float(self.bytes().split(b'\x00', 1)[0]))
        if tag == b'l':
            sign = self.take(1)
            value = int.from_bytes(self.take(self.length()*2), 'little')
            return self.register(-value if sign == b'-' else value)
        raise ValueError(f'未支持的 Ruby 数据标记 {tag!r}，位置 {self.pos-1}')

    def load(self):
        if self.take(2) != b'\x04\x08':
            raise ValueError('不是支持的 Ruby Marshal 4.8 数据')
        result = self.read()
        if self.pos != len(self.data):
            raise ValueError('Ruby 数据尾部含额外内容，可能是自定义封装')
        return result


def normalize_rgss(value, memo=None, active=None):
    """Convert RGSS objects into the same data shape used by the MV/MZ reader."""
    if memo is None:
        memo, active = {}, set()
    if isinstance(value, RubyString):
        return value.text()
    if not isinstance(value, (list, dict)):
        return value
    ident = id(value)
    if ident in active:
        return None
    if ident in memo:
        return memo[ident]
    active.add(ident)
    if isinstance(value, list):
        result = [normalize_rgss(v, memo, active) for v in value]
    elif '__opaque__' in value:
        result = None
    else:
        result = {}
        for key, child in value.items():
            if key == '__ruby_class__':
                continue
            if isinstance(key, RubyString):
                key = key.text()
            if isinstance(key, str):
                key = key.lstrip('@')
                key = re.sub(r'_([a-z])', lambda m: m[1].upper(), key)
                if key == 'condition':
                    key = 'conditions'
            result[key] = normalize_rgss(child, memo, active)
    active.remove(ident)
    memo[ident] = result
    return result


def read_rgss(path: Path):
    return normalize_rgss(MarshalReader(path.read_bytes()).load())
