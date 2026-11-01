"""Rebuild the small Windows helpers; does not run games or download tools."""
from pathlib import Path
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--zig', help='Path to zig.exe; alternatively use --cc')
parser.add_argument('--cc', default='i686-w64-mingw32-gcc')
args = parser.parse_args()
root = Path(__file__).resolve().parent / 'vendor/protected_reader'
output = root / 'bin'
output.mkdir(exist_ok=True)
compiler = [args.zig, 'cc', '-target', 'x86-windows-gnu'] if args.zig else [args.cc]
for name, flags in [('version.dll', ['-shared', str(root/'src/version.c'), str(root/'src/version.def'), '-lkernel32', '-luser32']),
                    ('launcher.exe', [str(root/'src/launcher.c'), '-lkernel32']),
                    ('isolation_check.exe', [str(root/'src/isolation_check.c'), '-ladvapi32', '-lws2_32'])]:
    subprocess.run([*compiler, '-O2', '-s', *flags, '-o', str(output/name)], check=True)
print('Reader helpers built in', output)
