"""Render an offscreen UI preview using invented demo dialogue only."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import sys
import shutil
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QFontDatabase, QFont
from app import MainWindow, STYLE
from ui_theme import apply_theme
from engine import Record, Result

app = QApplication([])
apply_theme(app)
for name in ('msyh.ttc', 'segoeui.ttf'):
    font = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'/name
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
app.setFont(QFont('Microsoft YaHei', 10))
app.setStyleSheet(STYLE.replace('Microsoft YaHei UI', 'Microsoft YaHei'))
rows = [
    ('地图 001 · 晨曦村', 'Map001/event1/page1', '事件 1 · 村口的约定 / 第 1 页', '对白', '莉娜', 'おはよう。今日はいよいよ出発だね。', '早上好，今天终于要出发了。'),
    ('地图 001 · 晨曦村', 'Map001/event1/page1', '事件 1 · 村口的约定 / 第 1 页', '对白', '旅行者', 'うん。忘れ物はないかな？', '嗯，没有落下什么东西吧？'),
    ('地图 001 · 晨曦村', 'Map001/event1/page1', '事件 1 · 村口的约定 / 第 1 页', '对白', '莉娜', '地図と手帳、それから君との約束。', '地图、手账，还有和你的约定。\n这些我都带上了。'),
    ('地图 001 · 晨曦村', 'Map001/event1/page1', '事件 1 · 村口的约定 / 第 1 页', '选项', '', '一緒に行こう', '一起出发吧'),
    ('地图 001 · 晨曦村', 'Map001/event1/page1', '事件 1 · 村口的约定 / 第 1 页', '选项', '', 'もう少し準備する', '再准备一下'),
    ('地图 001 · 晨曦村', 'Map001/event2/page1', '事件 2 · 旅店的问候 / 第 1 页', '对白', '店主', '道中、お気をつけて。', '一路小心。累了的话，这里随时欢迎你。'),
    ('地图 002 · 林间小径', 'Map002/event1/page1', '事件 1 · 风声与脚步 / 第 1 页', '对白', '莉娜', 'この道、昔と変わらないね。', '这条路，和小时候一样呢。'),
    ('地图 002 · 林间小径', 'Map002/event1/page1', '事件 1 · 风声与脚步 / 第 1 页', '对白', '旅行者', '少しゆっくり歩こうか。', '我们走慢一点吧，听听风声。'),
    ('公共事件', 'common/1', '公共事件 1 · 休息片刻', '对白', '莉娜', '少し休もう。', '休息一下吧，旅途才刚刚开始。'),
    ('数据库', 'database/Items', '物品 · Items', '物品', '', '旅の手帳', '旅行手账'),
]
result = Result('晨曦之旅 · 界面演示', 'RPG Maker MZ', '演示数据', '演示翻译.json')
for i,(group,sid,scene,category,speaker,original,translation) in enumerate(rows,1):
    r=Record(i,group,sid,scene,category,speaker,original,translation,original,translation,'已匹配',f'演示场景：记录 {i}')
    r.search='\n'.join((original,translation,speaker,scene)).casefold()
    result.records.append(r)
result.stats={'scenes':len({r.scene_id for r in result.records}),'records':len(rows),'categories':dict(Counter(r.category for r in result.records)),
              'statuses':{'已匹配':len(rows)},'translation_entries':len(rows),'unmatched_dictionary':0}
window=MainWindow()
window.resize(1440,850)
window.loaded(result)
window.export_button.setEnabled(True)
window.path.setText('演示游戏文件夹（此图不包含实际游戏内容）')
window.show()
app.processEvents()
window.tree.expandToDepth(1)
window.table.selectRow(2)
app.processEvents()
folder=Path(__file__).resolve().parent/'images'
folder.mkdir(exist_ok=True)
assert window.grab().save(str(folder/'preview.png'))
shutil.copy2(Path(__file__).resolve().parent.parent/'assets'/'icons'/'textlight-mascot-ui-v3.png', folder/'icon.png')
window.close()
print('Demo preview rendered')
