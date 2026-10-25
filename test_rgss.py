import json
import tempfile
import unittest
from pathlib import Path

from rgss import MarshalReader, normalize_rgss
from engine import extract, game_root


def integer(n):
    if n == 0:
        return b'\x00'
    if 0 < n < 123:
        return bytes([n + 5])
    if -124 < n < 0:
        return bytes([(n-5) & 255])
    size = max(1, (n.bit_length() + 7)//8)
    return bytes([size if n > 0 else 256-size]) + (n & ((1 << (size*8))-1)).to_bytes(size, 'little')


def symbol(s):
    raw = s.encode('utf-8')
    return b':' + integer(len(raw)) + raw


def encode(value):
    if value is None:
        return b'0'
    if value is True:
        return b'T'
    if value is False:
        return b'F'
    if isinstance(value, int):
        return b'i' + integer(value)
    if isinstance(value, str):
        raw = value.encode('utf-8')
        return b'I"' + integer(len(raw)) + raw + integer(1) + symbol('E') + b'T'
    if isinstance(value, list):
        return b'[' + integer(len(value)) + b''.join(encode(x) for x in value)
    if isinstance(value, tuple):
        klass, fields = value
        return b'o' + symbol(klass) + integer(len(fields)) + b''.join(symbol('@'+k)+encode(v) for k,v in fields.items())
    if isinstance(value, dict):
        return b'{' + integer(len(value)) + b''.join(encode(k)+encode(v) for k,v in value.items())
    raise TypeError(value)


class RgssTests(unittest.TestCase):
    def test_official_object_link_example(self):
        data = MarshalReader(b'\x04\x08[\x07"\x0ahello@\x06').load()
        self.assertIs(data[0], data[1])
        self.assertEqual(normalize_rgss(data), ['hello', 'hello'])

    def test_signed_numbers_and_symbol_links(self):
        fixtures = [(b'i\x00', 0), (b'i\x80', -123), (b'i\x7f', 122),
                    (b'i\xff\x00', -256), (b'i\x01\xff', 255), (b'i\xfe\x00\xff', -256)]
        for data, expected in fixtures:
            self.assertEqual(MarshalReader(b'\x04\x08'+data).load(), expected)
        self.assertEqual(MarshalReader(b'\x04\x08[\x07:\x0ahello;\x00').load(), ['hello', 'hello'])

    def test_encoding_binary_payload_and_cycle(self):
        data = MarshalReader(b'\x04\x08' + encode('汉化测试')).load()
        self.assertEqual(normalize_rgss(data), '汉化测试')
        opaque = b'\x04\x08u' + symbol('Table') + integer(4) + b'abcd'
        self.assertIsNone(normalize_rgss(MarshalReader(opaque).load()))
        self.assertEqual(normalize_rgss(MarshalReader(b'\x04\x08[\x06@\x00').load()), [None])

    def test_corrupt_data_rejected(self):
        for raw in [b'bad', b'\x04\x08@\x09', b'\x04\x08"\x7fshort', b'\x04\x08?']:
            with self.assertRaises(ValueError):
                MarshalReader(raw).load()

    def test_vx_ace_to_common_extraction_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'Data'
            data.mkdir()
            def write(name, value):
                (data/(name+'.rvdata2')).write_bytes(b'\x04\x08'+encode(value))
            write('System', ('RPG::System', {'game_title': '旧版游戏', 'terms': ('RPG::System::Terms', {'commands':['开始游戏']})}))
            write('MapInfos', {1: ('RPG::MapInfo', {'name': '村庄'})})
            command = lambda code, p: ('RPG::EventCommand', {'code':code, 'indent':0, 'parameters':p})
            write('Map001', ('RPG::Map', {'events': {2: ('RPG::Event', {'id':2, 'name':'招呼', 'pages':[
                ('RPG::Event::Page', {'condition':('RPG::Event::Page::Condition', {'switch1_valid':True,'switch1_id':5}),
                                    'list':[command(101,['',0,0,2]), command(401,['欢迎']),command(401,['旅行者']),command(102,[['谢谢']]),command(0,[])]})]})}}))
            tr = root/'翻译.json'
            tr.write_text(json.dumps({'欢迎\n旅行者':'你好，旅行者', '谢谢':'Thank you'}),encoding='utf-8')
            before = {p.name:p.read_bytes() for p in data.iterdir()}
            result = extract(str(root),str(tr))
            self.assertEqual(game_root(root), root)
            self.assertEqual(result.engine, 'RPG Maker VX Ace')
            dialogue = next(r for r in result.records if r.category == '对白')
            self.assertEqual(dialogue.translation,'你好，旅行者')
            self.assertEqual(dialogue.scene_id, 'Map001/event2/page1')
            self.assertIn('开关#5',dialogue.context)
            self.assertIn('.rvdata2:',dialogue.source)
            self.assertEqual(before,{p.name:p.read_bytes() for p in data.iterdir()})


if __name__ == '__main__':
    unittest.main()
