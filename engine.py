"""Read-only RPG Maker MV/MZ and MTool extraction. No game code is executed."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from rgss import read_rgss


STORY = {'对白', '滚动文字', '选项'}
NAME_TAG = re.compile(r'\\(?:n[cCrRlL]?|name)<([^>]+)>', re.I)


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def normalize(text: str) -> str:
    # Only normalize line endings; punctuation and spaces can carry meaning.
    return text.replace('\r\n', '\n').replace('\r', '\n')


def clean(text: str) -> str:
    text = NAME_TAG.sub('', text)
    text = re.sub(r'\\?<[Bb][Rr]\s*/?>', '\n', text)
    def variable(m):
        kind = {'v': '变量', 'n': '角色', 'p': '队员', 'i': '图标'}[m[1].lower()]
        return f'〔{kind}#{m[2]}〕'
    text = re.sub(r'\\([VNPI])\[(\d+)\]', variable, text, flags=re.I)
    text = re.sub(r'\\G\b', '〔货币单位〕', text, flags=re.I)
    text = re.sub(r'\\(?:C|FS)\[\d+\]', '', text, flags=re.I)
    text = re.sub(r'\\[.!|^><{}$]', '', text)
    return text.strip()


@dataclass(slots=True)
class Record:
    seq: int
    group: str
    scene_id: str
    scene: str
    category: str
    speaker: str
    original: str
    translation: str
    raw: str
    raw_translation: str
    status: str
    source: str
    context: str = ''
    search: str = ''

    @property
    def display(self):
        return self.translation or self.original


@dataclass
class Result:
    title: str
    engine: str
    root: str
    translation_file: str
    records: list[Record] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def game_root(path: str | Path) -> Path | None:
    path = Path(path).resolve()
    base = path.parent if path.is_file() else path
    candidates = [base, base / 'www']
    if base.name.lower() in ('data', 'js'):
        candidates.append(base.parent)
    for root in candidates:
        if (root / 'Data' / 'System.rvdata2').is_file() and (root / 'Data' / 'MapInfos.rvdata2').is_file():
            return root
        if (root / 'data' / 'System.json').is_file() and any(
            (root / 'js' / name).is_file() for name in ('rpg_core.js', 'rmmz_core.js')
        ):
            return root
    return None


NON_TRANSLATION_JSON = {'package.json', 'vk_swiftshader_icd.json', 'mtool_tilesetdefinedcache.json'}


def read_translation(path: Path) -> dict[str, str]:
    """Validate explicit selections and discovered files using the same rules."""
    if path.name.casefold() in NON_TRANSLATION_JSON:
        raise ValueError('所选文件是缓存或配置文件，不是翻译文件。请打开游戏 EXE／文件夹读取游戏内文本，或选择原文—译文 JSON 字典。')
    try:
        data = read_json(path)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError('无法读取这份翻译 JSON。请选择 UTF-8 编码的原文—译文字符串字典。') from error
    if not isinstance(data, dict) or not data:
        raise ValueError('这份 JSON 不包含有效的翻译字典。请打开游戏 EXE／文件夹读取游戏内文本，或选择非空的原文—译文字符串字典。')
    if any(not isinstance(v, str) for v in data.values()):
        raise ValueError('这份 JSON 不是当前支持的原文—译文字符串字典，可能是缓存或配置文件。请重新选择翻译文件，或打开游戏 EXE／文件夹。')
    return data


def translation_candidates(root: Path) -> list[Path]:
    """Scan shallow user-facing locations, never traverse game media/save directories."""
    bases = [root]
    if root.name.lower() == 'www':
        bases.insert(0, root.parent)
    paths = []
    for base in bases:
        paths.extend(base.glob('*.json'))
        for name in ('translations', 'translation', '翻译', '翻译文件'):
            folder = base / name
            if folder.is_dir():
                paths.extend(folder.glob('*.json'))
    valid = []
    for path in set(paths):
        try:
            read_translation(path)
        except (OSError, ValueError):
            # An unrelated, invalid or unreadable file must not block the game.
            continue
        valid.append(path)
    return sorted(valid, key=lambda p: (not any(x in p.name.lower() for x in ('翻译', 'trans', 'mtool')), p.name.lower()))


class Translator:
    def __init__(self, path: Path | None):
        self.path = path
        self.data: dict[str, str] = {}
        self.used: set[str] = set()
        self.index: dict[str, str] = {}
        if path:
            data = read_translation(path)
            self.data = data
            for key in data:
                self.index.setdefault(normalize(key), key)

    def find(self, text: str) -> str | None:
        key = text if text in self.data else self.index.get(normalize(text))
        if key is None or not self.data[key].strip():
            return None
        self.used.add(key)
        return self.data[key]

    def translate(self, text: str) -> tuple[str, str]:
        if not self.path:
            return '', '游戏内文本'
        exact = self.find(text)
        if exact is not None:
            return exact, '已匹配'
        lines = normalize(text).split('\n')
        translated = [self.find(line) if line.strip() else None for line in lines]
        found = sum(v is not None for v in translated)
        if not found:
            return '', '未匹配'
        joined = '\n'.join(v if v is not None else line for v, line in zip(translated, lines))
        # A name-box-only or formatting-only line does not leave untranslated dialogue.
        return joined, '已匹配' if all(v is not None or not clean(s) for v, s in zip(translated, lines)) else '部分匹配'


def page_conditions(page: dict) -> str:
    c = page.get('conditions', {})
    items = []
    for n in (1, 2):
        if c.get(f'switch{n}Valid'):
            items.append(f'开关#{c.get(f"switch{n}Id")} 开启')
    if c.get('variableValid'):
        items.append(f'变量#{c.get("variableId")} ≥ {c.get("variableValue")}')
    if c.get('selfSwitchValid'):
        items.append(f'独立开关 {c.get("selfSwitchCh")} 开启')
    if c.get('itemValid'):
        items.append(f'持有物品#{c.get("itemId")}')
    if c.get('actorValid'):
        items.append(f'角色#{c.get("actorId")} 在队伍中')
    return '；'.join(items)


def walk_strings(value, path=''):
    if isinstance(value, str):
        if value.strip():
            yield path, value
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_strings(child, f'{path}[{i}]')
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from walk_strings(child, f'{path}.{key}')


def json_from_js(source: str):
    """Accept comments/trailing commas in a data literal, without evaluating JS."""
    out = []
    i = 0
    quoted = False
    while i < len(source):
        c = source[i]
        if quoted:
            out.append(c)
            if c == '\\' and i + 1 < len(source):
                i += 1
                out.append(source[i])
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
            out.append(c)
        elif source.startswith('//', i):
            end = source.find('\n', i + 2)
            i = len(source) if end < 0 else end
            out.append('\n')
            continue
        elif source.startswith('/*', i):
            end = source.find('*/', i + 2)
            if end < 0:
                raise ValueError('插件列表含未闭合注释')
            i = end + 2
            out.append(' ')
            continue
        else:
            out.append(c)
        i += 1
    text = ''.join(out)
    out, i, quoted = [], 0, False
    while i < len(text):
        c = text[i]
        if quoted:
            out.append(c)
            if c == '\\' and i + 1 < len(text):
                i += 1
                out.append(text[i])
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
            out.append(c)
        elif c == ',':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j >= len(text) or text[j] not in ']}':
                out.append(c)
        else:
            out.append(c)
        i += 1
    data, _ = json.JSONDecoder().raw_decode(''.join(out).lstrip())
    return data


def extract(path: str, translation: str = '', progress: Callable | None = None,
            cancelled: Callable | None = None) -> Result:
    def tick(message):
        if cancelled and cancelled():
            raise InterruptedError('已取消提取。')
        if progress:
            progress(message)

    root = game_root(path)
    if root is None and not translation:
        if Path(path).suffix.lower() == '.json':
            translation = path
        else:
            raise ValueError('没有找到可读取的 RPG Maker MV／MZ／VX Ace 数据。请选择游戏主目录、www 目录或翻译 JSON。')
    tick('正在读取翻译文件…')
    tr = Translator(Path(translation) if translation else None)
    result = Result(Path(path).stem, '翻译字典', str(root or Path(path).parent), translation)

    def add(raw, group, scene_id, scene, category, source, speaker='', context='', untranslated=False):
        if not isinstance(raw, str) or not raw.strip():
            return
        translated, status = ('', '游戏内文本') if untranslated else tr.translate(raw)
        name_match = NAME_TAG.search(translated or raw)
        if name_match:
            speaker = name_match[1]
        elif speaker:
            speaker = tr.find(speaker) or speaker
        original = clean(raw)
        display_translation = clean(translated)
        if not original and not display_translation:
            return
        record = Record(len(result.records)+1, group, scene_id, scene, category, clean(speaker),
                        original, display_translation, raw, translated, status, source, context)
        record.search = '\n'.join((original, display_translation, raw, translated, record.speaker, scene, context)).casefold()
        result.records.append(record)

    def commands(cmds, group, sid, scene, source, condition=''):
        branches = {}
        speaker = ''
        i = 0
        while i < len(cmds):
            if i % 200 == 0:
                if cancelled and cancelled():
                    raise InterruptedError('已取消提取。')
            c = cmds[i]
            code, p, indent = c.get('code'), c.get('parameters', []), c.get('indent', 0)
            for depth in list(branches):
                if depth > indent:
                    del branches[depth]
            loc = f'{source}.list[{i}]'
            if code == 101:
                speaker = p[4] if len(p) > 4 and isinstance(p[4], str) else ''
            elif code == 105:
                speaker = ''
            elif code in (401, 405):
                lines = []
                j = i
                while j < len(cmds) and cmds[j].get('code') == code:
                    prm = cmds[j].get('parameters', [])
                    if prm and isinstance(prm[0], str):
                        lines.append(prm[0])
                    j += 1
                context = '；'.join(x for x in [condition, *[branches[d] for d in sorted(branches)]] if x)
                add('\n'.join(lines), group, sid, scene, '对白' if code == 401 else '滚动文字', loc,
                    speaker, context)
                i = j
                continue
            elif code == 102 and p and isinstance(p[0], list):
                for n, choice in enumerate(p[0]):
                    add(choice, group, sid, scene, '选项', f'{loc}.parameters[0][{n}]', context=condition)
            elif code == 402:
                value = p[1] if len(p) > 1 else str(p[0] if p else '')
                branches[indent] = '选择：' + clean(tr.find(str(value)) or str(value))
            elif code == 403:
                branches[indent] = '选择：取消'
            elif code == 111:
                branches[indent] = f'条件分支（指令 {i+1}，条件 {json.dumps(p, ensure_ascii=False)}）'
            elif code == 411:
                branches[indent] = f'否则分支（指令 {i+1}）'
            elif code in (404, 412):
                branches.pop(indent, None)
            elif code in (320, 324, 325) and len(p) > 1:
                add(p[1], group, sid, scene, '角色', loc, context=condition)
            elif code in (108, 408, 355, 655, 356, 357):
                category = '注释' if code in (108, 408) else '脚本／插件（待辨识）'
                for suffix, value in walk_strings(p):
                    add(value, group, sid, scene, category, f'{loc}.parameters{suffix}', context=condition)
            i += 1

    if root:
        ace = (root / 'Data' / 'System.rvdata2').is_file()
        data_dir = root / ('Data' if ace else 'data')
        extension = '.rvdata2' if ace else '.json'
        read_data = read_rgss if ace else read_json
        system = read_data(data_dir / ('System' + extension))
        result.title = system.get('gameTitle') or root.name
        result.engine = 'RPG Maker VX Ace' if ace else ('RPG Maker MZ' if (root / 'js' / 'rmmz_core.js').exists() else 'RPG Maker MV')
        try:
            map_infos = read_data(data_dir / ('MapInfos' + extension))
            map_names = ({i: m.get('name', '') for i, m in map_infos.items() if m} if isinstance(map_infos, dict)
                         else {m['id']: m.get('name', '') for m in map_infos if m})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            map_names = {}
            result.warnings.append(f'地图名称索引不可读：{exc}')
        files = sorted(data_dir.glob('*' + extension), key=lambda p: p.name)
        for n, file in enumerate(files):
            tick(f'正在读取 {n+1}/{len(files)} · {file.name}')
            logical_name = file.stem + '.json'
            if file.stem == 'Scripts':
                continue  # Compressed Ruby scripts are executable code, not a dialogue database.
            try:
                data = read_data(file)
            except (OSError, ValueError) as exc:
                result.warnings.append(f'{file.name} 未提取：{exc}')
                continue
            if re.fullmatch(r'Map\d+\.json', logical_name) and isinstance(data, dict):
                map_id = int(file.stem[3:])
                name = map_names.get(map_id) or data.get('displayName') or '未命名地图'
                name = clean(tr.find(name) or name)
                group = f'地图 {map_id:03d} · {name}'
                if data.get('displayName'):
                    add(data['displayName'], group, f'{file.stem}/title', '地图显示名称', '地图名称', f'{file.name}:displayName')
                events = data.get('events', [])
                if isinstance(events, dict):
                    events = [events[key] for key in sorted(events)]
                for event in events:
                    if not event:
                        continue
                    eid = event.get('id', 0)
                    ename = event.get('name') or '未命名事件'
                    ename = clean(tr.find(ename) or ename)
                    for page_idx, page in enumerate(event.get('pages', []), 1):
                        sid = f'{file.stem}/event{eid}/page{page_idx}'
                        scene = f'事件 {eid} · {ename} / 第 {page_idx} 页'
                        commands(page.get('list', []), group, sid, scene,
                                 f'{file.name}:events[{eid}].pages[{page_idx-1}]', page_conditions(page))
            elif logical_name == 'CommonEvents.json' and isinstance(data, list):
                for event in data:
                    if event:
                        eid = event.get('id', 0)
                        name = event.get('name') or '未命名公共事件'
                        name = clean(tr.find(name) or name)
                        commands(event.get('list', []), '公共事件', f'common/{eid}', f'公共事件 {eid} · {name}',
                                 f'{file.name}:[{eid}]', f'触发类型 {event.get("trigger", 0)}；开关#{event.get("switchId", 0)}')
            elif logical_name == 'Troops.json' and isinstance(data, list):
                for troop in data:
                    if troop:
                        tid = troop.get('id', 0)
                        for pn, page in enumerate(troop.get('pages', []), 1):
                            commands(page.get('list', []), '战斗事件', f'troop/{tid}/{pn}',
                                     f'敌群 {tid} · {troop.get("name", "")} / 第 {pn} 页',
                                     f'{file.name}:[{tid}].pages[{pn-1}]',
                                     '战斗条件：' + json.dumps(page.get('conditions', {}), ensure_ascii=False))
            elif logical_name == 'System.json':
                for key in ('gameTitle', 'currencyUnit', 'armorTypes', 'elements', 'equipTypes', 'skillTypes', 'weaponTypes', 'terms'):
                    for suffix, value in walk_strings(data.get(key), key):
                        add(value, '数据库', 'database/System', '系统与菜单', '菜单／系统', f'{file.name}:{suffix}')
            elif logical_name in ('Actors.json', 'Classes.json', 'Items.json', 'Weapons.json', 'Armors.json', 'Skills.json', 'States.json', 'Enemies.json'):
                category = {'Actors.json': '角色', 'Classes.json': '职业', 'Items.json': '物品', 'Weapons.json': '装备',
                            'Armors.json': '装备', 'Skills.json': '技能', 'States.json': '状态', 'Enemies.json': '敌人'}[logical_name]
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    for key in ('name', 'nickname', 'profile', 'description', 'message1', 'message2', 'message3', 'message4', 'note'):
                        if item.get(key):
                            add(item[key], '数据库', f'database/{file.stem}', f'{category} · {file.stem}',
                                '备注（待辨识）' if key == 'note' else category, f'{file.name}:[{item.get("id", 0)}].{key}')
            elif logical_name not in ('MapInfos.json', 'Animations.json') and not file.stem.startswith('!'):
                for suffix, value in walk_strings(data):
                    add(value, '其他数据', f'other/{file.stem}', file.stem, '其他数据（待辨识）', f'{file.name}:{suffix}')
        # Plugins are plain text input only. We never import or evaluate game JavaScript.
        plugin_file = root / 'js' / 'plugins.js'
        if plugin_file.exists():
            tick('正在读取插件参数…')
            try:
                source = plugin_file.read_text(encoding='utf-8-sig')
                match = re.search(r'\$plugins\s*=\s*', source)
                if not match:
                    raise ValueError('未找到标准插件列表')
                plugins = json_from_js(source[match.end():])
                for plugin in plugins:
                    if plugin.get('status'):
                        name = str(plugin.get('name', '插件'))
                        for suffix, value in walk_strings(plugin.get('parameters', {})):
                            add(value, '插件参数', f'plugin/{name}', name, '脚本／插件（待辨识）', f'js/plugins.js:{name}{suffix}')
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                result.warnings.append(f'插件参数未提取：{exc}')
        result.warnings.append('插件脚本中的动态文字、图片文字和自定义加密数据可能未覆盖。待辨识类别可能含内部参数或注释。')
        if ace:
            result.warnings.append('VX Ace：读取已展开的 .rvdata2；未读取 Scripts.rvdata2 中的压缩 Ruby 脚本，也未读取存档。')
    tick('正在保留未关联场景的翻译…')
    unused = 0
    for key, value in tr.data.items():
        if key not in tr.used:
            unused += 1
            add(key, '未关联场景', 'unmatched', '翻译字典 · 未关联场景', '未关联场景', f'{Path(translation).name}:条目 {unused}')
        if unused % 1000 == 0 and cancelled and cancelled():
            raise InterruptedError('已取消提取。')
    result.stats = {'records': len(result.records), 'scenes': len({r.scene_id for r in result.records}),
                    'translation_entries': len(tr.data), 'unmatched_dictionary': unused,
                    'categories': dict(Counter(r.category for r in result.records)),
                    'statuses': dict(Counter(r.status for r in result.records))}
    if not result.records:
        result.warnings.append('没有提取到文本，请检查游戏数据或翻译文件。')
    tick('提取完成')
    return result
