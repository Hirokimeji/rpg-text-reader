"""Read-only SRPG Studio adapter using the bundled MIT SRPG-ToolBox parser.

Only the project-data segment is copied into an isolated temporary directory.
No game executable, game script, resource unpacking or patch application is run.
Archive layout reference: Sinflower/SRPG-ToolBox (see vendor/srpg/README.md).
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PARSER_SHA256 = 'bf38aace603d1852e1684e8ae0505f6c35b4c912c46bbd9fda78377ff97f6462'
MAX_PROJECT_BYTES = 256 * 1024 * 1024
EVENT_LABELS = {
    'openingEvents': '开场事件', 'endingEvents': '结束事件',
    'autoEvents': '自动事件', 'placeEvents': '地点事件',
    'talkEvents': '对话事件', 'communicationEvents': '交流事件',
    'events': '角色事件', 'EnemyUnits': '敌方单位', 'AllyUnits': '友方单位',
    'EvEnemyUnits': '增援敌方单位', 'EvAllyUnits': '增援友方单位',
    'GuestUnits': '访客单位',
}
DATABASE_LABELS = {
    'players': '角色', 'bookmark': '角色', 'weapons': '装备', 'items': '物品',
    'skills': '技能', 'states': '状态', 'classes': '职业', 'races': '种族',
    'titles': '菜单／系统', 'strings': '菜单／系统',
}


def is_srpg(root: Path) -> bool:
    try:
        with (root / 'data.dts').open('rb') as stream:
            return stream.read(4) == b'SDTS'
    except OSError:
        return False


def clean_srpg(text: str) -> str:
    # SRPG has its own variable syntax; do not apply RPG Maker substitutions.
    text = re.sub(r'\\(?:C|F|font|fs|fw|fi|ts|tu|wa|at|sp)\[\d+\]', '', text, flags=re.I)
    text = re.sub(r'\\vo\[[^\]\r\n]*\]', '', text)
    return re.sub(r'\\[._]', '', text).strip()


def project_data(path: Path) -> tuple[int, int, bytes]:
    with path.open('rb') as stream:
        header = stream.read(168)
        if len(header) < 168 or header[:4] != b'SDTS':
            raise ValueError('SRPG Studio 的 data.dts 文件头无效或文件不完整。')
        _, encrypted, version, _, segments, relative = struct.unpack_from('<6I', header)
        if not 1140 <= version <= 1322:
            raise ValueError(f'暂不支持这份 SRPG Studio 数据版本（{version}）；当前适配 1.140–1.322 的标准未加密 SDTS 数据。')
        if encrypted:
            raise ValueError('这份 SRPG Studio data.dts 已加密；当前版本仅支持未加密的标准 SDTS 项目数据。')
        offset = 168 + relative
        size = path.stat().st_size - offset
        if size < 16 or size > MAX_PROJECT_BYTES:
            raise ValueError('SRPG Studio 项目区段越界、不完整或超过 256 MB 读取上限。')
        stream.seek(offset)
        data = stream.read(size)
        if len(data) != size:
            raise ValueError('读取 SRPG Studio 数据时文件发生变化，请重新打开游戏目录。')
    return version, segments, data


def parser_path() -> Path:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    path = base / 'vendor' / 'srpg' / 'SRPG_Unpacker.exe'
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != PARSER_SHA256:
        raise ValueError('SRPG Studio 解析组件缺失或校验失败，请重新下载完整的台词拾光便携版。')
    return path


def run_parser(project: Path, output: Path, tick, timeout=120):
    helper = parser_path()
    log_path = project.parent / 'parser.log'
    with log_path.open('wb') as log:
        process = subprocess.Popen(
            [str(helper), str(project), '-c', '-o', str(output)],
            cwd=project.parent, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        start = time.monotonic()
        try:
            while process.poll() is None:
                tick('正在解析 SRPG Studio 地图与事件…')
                if time.monotonic() - start > timeout:
                    raise ValueError('SRPG Studio 解析超时（120 秒），这份数据可能包含尚未适配的结构。')
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    if process.returncode != 0 or not (output / 'titles.json').is_file():
        # The helper can report details about unsupported command structures.
        with log_path.open('rb') as log:
            log.seek(max(0, log_path.stat().st_size - 1200))
            detail = log.read().decode('utf-8', errors='replace').strip()
        raise ValueError('SRPG Studio 项目解析失败，可能含尚未支持的事件或数据结构。\n' + detail)


def emit_document(document, relative: str, add, tick):
    """Convert Toolbox's structural JSON to the application's record model."""
    file = Path(relative)
    base_id = 'srpg/' + relative.removesuffix('.json')
    category = DATABASE_LABELS.get(file.stem, '其他数据（待辨识）')
    if relative.startswith('Maps/') and isinstance(document, dict):
        name = document.get('name') or document.get('mapName') or '未命名地图'
        group = f'地图 {document.get("id", 0):03d} · {name}'
        category = '地图信息'
    elif file.stem in ('bookmarkevents', 'mapcommonevents'):
        group = '公共事件'
    elif relative.startswith('Base/'):
        group = '据点事件与数据'
    elif relative.startswith('Extra/'):
        group = '回想与附加事件'
    else:
        group = '数据库'

    def emit(text, path, kind, sid, scene, speaker='', record_group=None):
        if isinstance(text, str) and text.strip():
            add(text, record_group or group, sid, scene, kind, f'data.dts:{relative}:{path}', speaker)

    def command_rows(command, path, sid, scene, event_group):
        if not isinstance(command, dict):
            return
        kind = {'message': '对白', 'choice': '选项', 'script': '脚本／插件（待辨识）'}.get(command.get('type'), '其他数据（待辨识）')
        speaker = command.get('speaker', '')
        if not isinstance(speaker, str) or speaker == 'No Speaker' or speaker.startswith(('Unknown_', 'Invalid Type:')):
            speaker = ''
        for index, text in enumerate(command.get('data', [])):
            emit(text, f'{path}.data[{index}]', kind, sid, scene, speaker, event_group)
        for key, text in command.items():
            if key in ('data', 'speaker', 'type', 'id'):
                continue
            kind = '注释' if key == 'comment' else ('对白' if key == 'infoText' else '其他数据（待辨识）')
            emit(text, f'{path}.{key}', kind, sid, scene, record_group=event_group)

    def walk(node, path='$', context=''):
        if isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f'{path}[{i}]', context)
        elif isinstance(node, dict):
            if isinstance(node.get('pages'), list) and all(
                isinstance(page, dict) and isinstance(page.get('commands'), list) for page in node['pages']
            ):
                tick('正在整理 SRPG Studio 场景…')
                event_name = node.get('name') or '未命名事件'
                event_title = f'{context} · 事件 {node.get("id", 0)} · {event_name}'.strip(' ·')
                event_id = f'{base_id}/{path}/event{node.get("id", 0)}'
                event_group = '角色事件' if group == '数据库' else group
                for index, page in enumerate(node['pages']):
                    sid = f'{event_id}/page{index+1}'
                    scene = f'{event_title} / 第 {index+1} 页'
                    for ci, command in enumerate(page.get('commands', [])):
                        command_rows(command, f'{path}.pages[{index}].commands[{ci}]', sid, scene, event_group)
                for key, value in node.items():
                    if key != 'pages':
                        kind = '脚本／插件（待辨识）' if key == 'customParameters' else '事件信息'
                        emit(value, f'{path}.{key}', kind, event_id + '/metadata', event_title + ' · 信息', record_group=event_group)
                return
            owner = node.get('name', '') if 'events' in node else ''
            for key, value in node.items():
                if key in ('id', 'type', 'speaker', 'fontName'):
                    continue
                next_context = ' · '.join(s for s in (context, owner, EVENT_LABELS.get(key, '')) if s)
                if isinstance(value, str):
                    kind = '脚本／插件（待辨识）' if key == 'customParameters' else category
                    emit(value, f'{path}.{key}', kind, base_id + '/metadata', context or file.stem)
                else:
                    walk(value, f'{path}.{key}', next_context)
        elif isinstance(node, str):
            emit(node, path, category, base_id + '/metadata', context or file.stem)

    walk(document)


def extract_srpg(root: Path, add, tick):
    tick('正在读取 SRPG Studio 项目区段…')
    version, segments, data = project_data(root / 'data.dts')
    with tempfile.TemporaryDirectory(prefix='textlight-srpg-') as folder:
        work = Path(folder)
        project = work / 'project.dat'
        project.write_bytes(data)
        (work / 'config.json').write_text(json.dumps({'fileVersion': version, 'segments': segments}), encoding='utf-8')
        output = work / 'text'
        run_parser(project, output, tick)
        files = sorted(output.rglob('*.json'))
        title = root.name
        for index, file in enumerate(files):
            tick(f'正在整理 SRPG Studio 文本 {index+1}/{len(files)}…')
            relative = file.relative_to(output).as_posix()
            document = json.loads(file.read_text(encoding='utf-8-sig'))
            if relative == 'titles.json':
                title = document.get('gameTitle') or document.get('windowTitle') or title
            emit_document(document, relative, add, tick)
    return title, version
