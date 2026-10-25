"""Read-only Unity resource/text adapter. Managed DLLs are parsed as metadata.

Uses UnityPy 1.25.3 and TypeTreeGeneratorAPI 0.0.10. No game code is loaded
into a CLR or executed. Embedded type trees are preferred; stripped Mono trees
can be recovered from the game's Managed directory.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path


RICH_TEXT = re.compile(r'</?(?:size|color|b|i|u|s|sup|sub|align|font|material|mark|nobr|noparse|indent|line-height|pos|space|voffset|cspace)(?:[ =][^<>]*)?>', re.I)
CONTENT_KEYS = ('Text', 'text', 'Message', 'message', 'DialogueText', 'dialogueText', 'content', 'Content', 'sentence')
SPEAKER_KEYS = ('Speaker', 'speaker', 'speakerName', 'Name', 'name', 'CharacterName', 'characterName')
TEXT_FIELDS = {'m_Text', 'm_text', 'm_Localized', 'text', 'Text', 'message', 'Message', 'description', 'Description',
               'tooltip', 'Tooltip', 'displayName', 'DisplayName', 'ChoiceText', 'choiceText', 'SEDescription', 'title', 'Title'}
HEADER_FIELDS = {'m_GameObject', 'm_Enabled', 'm_Script', 'm_Name'}


def clone_node(node):
    # UnityPy's native TypeTreeNode does not implement the pickle protocol.
    from UnityPy.helpers.TypeTreeNode import TypeTreeNode
    result = TypeTreeNode(node.m_Level, node.m_Type, node.m_Name, 0, 0, m_MetaFlag=node.m_MetaFlag)
    result.m_Children = [clone_node(child) for child in node.m_Children]
    return result


def clean_unity(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = RICH_TEXT.sub('', text)
    text = re.sub(r'\{(?:pause|delay)\s*:\s*\d+\}', '', text, flags=re.I)
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def unity_data(root: Path) -> Path | None:
    def valid(folder):
        return folder.is_dir() and ((folder / 'globalgamemanagers').is_file() or (folder / 'data.unity3d').is_file())
    if root.name.casefold().endswith('_data') and valid(root):
        return root
    matches = [p for p in root.glob('*_Data') if valid(p)] if root.is_dir() else []
    # Ambiguous parent directories are not silently assigned to one game.
    return matches[0] if len(matches) == 1 else None


def asset_identity(asset_file):
    parts, seen = [], set()
    current = asset_file
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = getattr(current, 'name', '')
        if name:
            parts.append(str(name).replace('\\', '/'))
        current = getattr(current, 'parent', None)
    return '/'.join(reversed(parts))


def natural_key(text):
    return [(0, int(p)) if p.isdigit() else (1, p.casefold()) for p in re.split(r'(\d+)', str(text))]


def first_string(data, keys):
    return next((data[k] for k in keys if isinstance(data.get(k), str) and data[k].strip()), '')


def emit_text_tree(tree, name: str, identity: str, source: str, add, *, class_name='', tick=lambda _: None):
    """Recognize structured dialogue; keep other text outside the story filter."""
    story = any(s in class_name.casefold() for s in ('dialogue', 'dialog', 'conversation', 'scenario', 'story', 'talk'))
    scene = first_string(tree, ('DialogueName', 'dialogueName', 'conversationName', 'm_Name')) if isinstance(tree, dict) else ''
    scene = scene or name
    rows_emitted = 0

    def put(text, path, category, speaker='', context=''):
        nonlocal rows_emitted
        if isinstance(text, str) and text.strip():
            group = 'Unity 剧本' if category in ('对白', '选项') else ('Unity 注释与事件' if category == '注释' else 'Unity 其他文本')
            add(text, group, identity, scene, category, source + ':' + path, speaker, context)
            rows_emitted += 1

    def dialogue_rows(rows, path):
        for index, row in enumerate(rows):
            if index % 100 == 0:
                tick('正在整理 Unity 对白…')
            if not isinstance(row, dict):
                continue
            loc = f'{path}[{index}]'
            text_key = next((k for k in CONTENT_KEYS if isinstance(row.get(k), str)), None)
            if text_key:
                put(row[text_key], loc + '.' + text_key, '对白', first_string(row, SPEAKER_KEYS))
            for choice_key in ('choices', 'Choices', 'options', 'Options'):
                choices = row.get(choice_key)
                if not isinstance(choices, list):
                    continue
                for ci, choice in enumerate(choices):
                    if isinstance(choice, str):
                        put(choice, f'{loc}.{choice_key}[{ci}]', '选项')
                    elif isinstance(choice, dict):
                        key = next((k for k in ('ChoiceText', 'choiceText', *CONTENT_KEYS) if isinstance(choice.get(k), str)), None)
                        if key:
                            condition = first_string(choice, ('ChoiceCondition', 'condition', 'Condition'))
                            put(choice[key], f'{loc}.{choice_key}[{ci}].{key}', '选项', context=condition)
            # Preserve staging notes without putting them between dialogue lines.
            if isinstance(row.get('SEDescription'), str):
                put(row['SEDescription'], loc + '.SEDescription', '注释')

    def walk(value, path='$', hint=False):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('m_Name', 'm_Script', 'm_GameObject', 'm_EditorClassIdentifier'):
                    continue
                is_dialogue = hint or key.casefold() in ('dialogue', 'dialogueline', 'dialoguelines', 'lines', 'conversations')
                if isinstance(child, list) and (is_dialogue or story) and any(
                    isinstance(x, dict) and any(isinstance(x.get(k), str) for k in CONTENT_KEYS) for x in child
                ):
                    dialogue_rows(child, path + '.' + key)
                elif isinstance(child, str) and key in TEXT_FIELDS:
                    put(child, path + '.' + key, '注释' if key == 'SEDescription' else '其他文本（待辨识）')
                elif isinstance(child, (dict, list)):
                    walk(child, path + '.' + key, is_dialogue)
        elif isinstance(value, list):
            if (hint or story) and any(isinstance(x, dict) and any(isinstance(x.get(k), str) for k in CONTENT_KEYS) for x in value):
                dialogue_rows(value, path)
            else:
                for index, child in enumerate(value):
                    walk(child, f'{path}[{index}]', hint)

    walk(tree, hint=story)
    return rows_emitted


def decode_text(raw: bytes) -> str:
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    text = raw.decode('utf-8-sig')
    if '\x00' in text or sum(ord(c) < 32 and c not in '\r\n\t' for c in text) > 3:
        raise ValueError('二进制内容，不作为文本读取')
    return text


def emit_text_asset(raw: bytes, name, identity, source, add, tick):
    text = decode_text(raw)
    if not text.strip():
        return
    suffix = Path(name).suffix.casefold()
    if suffix == '.json' or text.lstrip().startswith(('{', '[')):
        try:
            tree = json.loads(text)
        except ValueError:
            tree = None
        if tree is not None:
            count = emit_text_tree(tree, name, identity, source, add, class_name='Dialogue' if re.search('dialog|story|scenario', name, re.I) else '', tick=tick)
            if count:
                return
            # Flat localization dictionaries can use arbitrary string IDs.
            if isinstance(tree, dict) and tree and all(isinstance(v, str) for v in tree.values()):
                for key, value in tree.items():
                    if value.strip():
                        add(value, 'Unity 文本资源', identity, name, '其他文本（待辨识）', source + ':$[' + json.dumps(key, ensure_ascii=False) + ']')
                return
    if suffix in ('.csv', '.tsv'):
        rows = list(csv.DictReader(io.StringIO(text), delimiter='\t' if suffix == '.tsv' else ','))
        if rows:
            lower = {k.casefold(): k for k in rows[0] if k}
            text_key = next((lower[k] for k in ('text', 'message', 'dialogue', 'content') if k in lower), None)
            if text_key:
                speaker_key = next((lower[k] for k in ('speaker', 'name', 'character') if k in lower), None)
                for i, row in enumerate(rows):
                    value = row.get(text_key)
                    if value:
                        add(value, 'Unity 文本资源', identity, name, '对白', f'{source}:row[{i+2}].{text_key}', row.get(speaker_key, '') or '' if speaker_key else '')
                return
    # Unrecognized text is retained verbatim, never guessed to be a story scene.
    add(text, 'Unity 文本资源', identity, name, '其他文本（待辨识）', source)


class ManagedReader:
    """Generate field layouts from metadata, with exact-length validation."""
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.generators = {}
        self.nodes = {}
        self.scripts = {}

    def script_info(self, obj):
        base = obj.read(check_read=False)
        script = base.m_Script
        key = (id(obj.assets_file), script.m_FileID, script.m_PathID)
        if key not in self.scripts:
            ms = script.deref(obj.assets_file).read()
            namespace = ms.m_Namespace or ''
            full = f'{namespace}.{ms.m_ClassName}' if namespace else ms.m_ClassName
            self.scripts[key] = (full, ms.m_AssemblyName)
        return self.scripts[key], base.m_Name or ''

    def node(self, version, full, assembly, payload=False):
        from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
        key = (version, full, assembly, payload)
        if key in self.nodes:
            return self.nodes[key]
        if version not in self.generators:
            folder = self.data_dir / 'Managed'
            if not folder.is_dir():
                raise ValueError('类型树缺失，且没有可用的 Managed 元数据；此类 IL2CPP／裁剪数据暂不支持')
            generator = TypeTreeGenerator(version)
            generator.load_local_dll_folder(str(folder))
            self.generators[version] = generator
        node = clone_node(self.generators[version].get_nodes_up(assembly, full))

        def repair(n):
            if n.m_Type == 'string' and n.m_Children and n.m_Children[0].m_Type == 'Array':
                children = n.m_Children[0].m_Children
                if len(children) > 1 and children[1].m_Type != 'char':
                    n.m_Type = 'vector'
            for child in n.m_Children:
                repair(child)
        repair(node)
        if payload:
            children = list(node.m_Children)
            while children and children[0].m_Name in HEADER_FIELDS:
                children.pop(0)
            node.m_Children = children
        self.nodes[key] = node
        return node

    def read(self, obj, full, assembly):
        from UnityPy.helpers import TypeTreeHelper
        if obj.serialized_type and obj.serialized_type.node:
            return obj.read_typetree(check_read=True)
        version = str(obj.assets_file.unity_version)
        node = self.node(version, full, assembly)
        registries = [n for n in node.m_Children if n.m_Type == 'ManagedReferencesRegistry']
        if not registries:
            return obj.read_typetree(node, check_read=True)
        node = clone_node(node)
        node.m_Children = [n for n in node.m_Children if n.m_Type != 'ManagedReferencesRegistry']
        obj.reset()
        reader = obj.reader
        end = reader.Position + obj.byte_size
        data = TypeTreeHelper.read_typetree(node, reader, as_dict=True, check_read=False, assetsfile=obj.assets_file)

        def string():
            length = reader.read_int()
            if not 0 <= length <= 2048 or reader.Position + length > end:
                raise ValueError('托管引用的类型名称越界')
            value = reader.read_bytes(length).decode('utf-8')
            reader.align_stream()
            return value
        refs = {}
        if reader.Position + 8 > end or reader.read_int() != 2:
            raise ValueError('暂不支持这种托管引用注册表版本')
        count = reader.read_int()
        if not 0 <= count <= 100000:
            raise ValueError('托管引用数量无效')
        for _ in range(count):
            rid = reader.read_long()
            cls, namespace, asm = string(), string(), string()
            if not cls:
                refs[rid] = None
                continue
            fullname = namespace + '.' + cls if namespace else cls
            layout = self.node(version, fullname, asm or assembly, payload=True)
            value = TypeTreeHelper.read_value(layout, reader, TypeTreeHelper.TypeTreeConfig(True, obj.assets_file, False))
            refs[rid] = value
        if reader.Position != end:
            raise ValueError(f'托管引用解析未完整对应对象长度（差 {end-reader.Position} 字节）')

        def expand(value, seen=frozenset(), depth=0):
            if depth > 64:
                raise ValueError('托管引用嵌套过深')
            if isinstance(value, dict):
                if set(value) == {'rid'}:
                    rid = value['rid']
                    if rid == -2:
                        return None
                    if rid in seen:
                        return None  # Reference cycles carry no new inline text.
                    if rid not in refs:
                        raise ValueError('托管引用指向缺失对象')
                    return expand(refs[rid], seen | {rid}, depth+1)
                return {k: expand(v, seen, depth+1) for k, v in value.items()}
            if isinstance(value, list):
                return [expand(v, seen, depth+1) for v in value]
            return value
        return expand(data)


def extract_unity(root: Path, add, tick):
    import UnityPy
    from UnityPy.helpers import TypeTreeHelper
    data_dir = unity_data(root)
    if data_dir is None:
        raise ValueError('未找到唯一的 Unity *_Data 游戏数据目录。请选择具体游戏目录。')
    warnings = ['Unity：按资源对象／剧本分组，排列不代表游戏运行时的剧情顺序；图片、加密资源和动态拼接文字不在当前支持范围。']
    files = [p for p in data_dir.iterdir() if p.is_file() and (p.suffix.casefold() in ('.assets', '.unity3d', '.bundle') or re.fullmatch(r'level\d+|globalgamemanagers', p.name))]
    streaming = data_dir / 'StreamingAssets'
    external = []
    if streaming.is_dir():
        for p in sorted(streaming.rglob('*')):
            if not p.is_file():
                continue
            suffix = p.suffix.casefold()
            if suffix in ('.txt', '.json', '.csv', '.tsv', '.xml', '.bytes'):
                external.append(p)
            elif suffix in ('.bundle', '.unity3d', '.assets'):
                files.append(p)
    if not files and not external:
        raise ValueError('没有找到当前支持的 Unity 资源或外置文本文件。')
    reader = ManagedReader(data_dir)
    previous_boost = TypeTreeHelper.read_typetree_boost
    TypeTreeHelper.read_typetree_boost = None
    problems = Counter()
    stats = Counter()
    classes = Counter()
    try:
        tick('正在载入 Unity 资源，较大的资源包可能需要一些时间…')
        env = UnityPy.load(*(str(p) for p in sorted(files))) if files else None
        objects = list(env.objects) if env else []
        targets = []
        for i, obj in enumerate(objects):
            if i % 200 == 0:
                tick(f'正在识别 Unity 文本对象 {i+1:,}/{len(objects):,}…')
            if obj.type.name == 'TextAsset':
                targets.append(('', '', '', obj))
            elif obj.type.name == 'MonoBehaviour':
                try:
                    (full, assembly), name = reader.script_info(obj)
                    if re.search(r'dialog|conversation|localiz|language|text|message|talk|story|scenario|event|npc', full, re.I):
                        targets.append((name, full, assembly, obj))
                except Exception as exc:
                    problems['对象类型不可读 · ' + type(exc).__name__] += 1
        for index, (name, full, assembly, obj) in enumerate(sorted(targets, key=lambda x: (natural_key(x[0]), x[3].path_id))):
            tick(f'正在提取 Unity 文本 {index+1:,}/{len(targets):,}…')
            asset_name = asset_identity(obj.assets_file)
            identity = f'unity/{asset_name}/{obj.path_id}'
            source = f'{data_dir.name}/{asset_name}:pathID={obj.path_id}'
            try:
                if obj.type.name == 'TextAsset':
                    text_asset = obj.read()
                    name = text_asset.m_Name or str(obj.path_id)
                    raw = text_asset.m_Script
                    if isinstance(raw, str):
                        raw = raw.encode('utf-8', errors='surrogateescape')
                    try:
                        emit_text_asset(raw, name, identity, source, add, tick)
                    except (UnicodeError, ValueError):
                        # Unity TextAssets also store arbitrary binary payloads.
                        stats['binary_text_assets_skipped'] += 1
                        continue
                    stats['text_assets'] += 1
                else:
                    tree = reader.read(obj, full, assembly)
                    emit_text_tree(tree, name or full, identity, source, add, class_name=full, tick=tick)
                    stats['managed_objects'] += 1
                    classes[full] += 1
                    if 'dialogue' in full.casefold():
                        stats['dialogue_objects'] += 1
            except InterruptedError:
                raise
            except Exception as exc:
                problems[full + ' · ' + type(exc).__name__] += 1
        for p in external:
            tick(f'正在读取 Unity 外置文本 · {p.name}')
            try:
                if p.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError('文本文件超过 32 MB')
                relative = p.relative_to(data_dir).as_posix()
                emit_text_asset(p.read_bytes(), p.name, 'unity/external/' + relative, relative, add, tick)
                stats['external_files'] += 1
            except InterruptedError:
                raise
            except (OSError, UnicodeError, ValueError, csv.Error) as exc:
                problems['外置文本 · ' + type(exc).__name__] += 1
    finally:
        TypeTreeHelper.read_typetree_boost = previous_boost
    if problems:
        warnings.append(f'Unity：{sum(problems.values()):,} 个候选对象／文件未读取；不代表这些对象都含对白。' + '；'.join(f'{k} ×{v}' for k, v in problems.most_common(6)))
    title = root.name.removesuffix('_Data')
    info = data_dir / 'app.info'
    if info.is_file():
        lines = info.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        if len(lines) >= 2 and lines[1].strip():
            title = lines[1].strip()
    details = dict(stats)
    details['decoded_classes'] = dict(classes)
    return title, warnings, details
