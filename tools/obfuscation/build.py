"""Build native Python modules and protected browser assets, without source files."""
from pathlib import Path
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ('core/lunel_core', 'console/api/lunel_console', 'worker/lunel_worker')


def run(*args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def compile_tree(directory):
    from Cython.Build import cythonize
    from Cython.Compiler import Options
    from setuptools import Extension, Distribution

    Options.docstrings = False

    extensions = []
    for file in directory.rglob('*.py'):
        rel = file.relative_to(directory).with_suffix('')
        parts = list(rel.parts)
        # Keep the package initializer's qualified name.
        name = '.'.join(parts)
        extensions.append(Extension(name, [str(file)], extra_compile_args=['-O2', '-g0']))
    modules = cythonize(extensions, quiet=True, compiler_directives={
        'language_level': 3, 'annotation_typing': False, 'binding': True,
        'embedsignature': False, 'emit_code_comments': False,
    })
    dist = Distribution({'ext_modules': modules})
    command = dist.get_command_obj('build_ext')
    command.build_lib = str(directory)
    command.build_temp = str(directory / '_build')
    command.ensure_finalized()
    command.run()
    for file in directory.rglob('*'):
        if file.suffix in ('.so', '.pyd'):
            if sys.platform == 'darwin':
                run('strip', '-x', str(file))
            elif sys.platform.startswith('linux'):
                run('strip', '--strip-unneeded', str(file))
    for file in list(directory.rglob('*')):
        if file.is_file() and file.suffix in ('.py', '.c', '.h', '.o'):
            file.unlink()
    shutil.rmtree(directory / '_build', ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/obfuscated')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; choose a new directory.')
    with tempfile.TemporaryDirectory(prefix='lunel-build-') as temporary:
        stage = Path(temporary)
        for package in PACKAGES:
            shutil.copytree(ROOT / package, stage / package,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT / 'console/frontend', stage / 'console/frontend')
        for name in ('main.py', 'panel.py', 'requirements.txt', 'LICENSE'):
            shutil.copy2(ROOT / name, stage / name)
        for component in ('core', 'console/api', 'worker'):
            shutil.copy2(ROOT / component / 'requirements.txt', stage / component / 'requirements.txt')
        run('node', str(Path(__file__).with_name('obfuscate.mjs')), str(stage))
        # runpy cannot execute extension modules; tiny public launchers delegate
        # to native implementations and preserve python -m / python main.py.
        for package in PACKAGES:
            entry = stage / package / '__main__.py'
            entry.rename(entry.with_name('_entry.py'))
        (stage / 'main.py').rename(stage / '_lunel_boot.py')
        for component in ('core', 'console/api', 'worker'):
            compile_tree(stage / component)
        # Compile root modules separately so package roots are preserved.
        with tempfile.TemporaryDirectory(prefix='lunel-root-') as root_temp:
            root_stage = Path(root_temp)
            for name in ('_lunel_boot.py', 'panel.py'):
                shutil.move(stage / name, root_stage / name)
            compile_tree(root_stage)
            for file in root_stage.iterdir():
                shutil.move(file, stage / file.name)
        for package in PACKAGES:
            (stage / package / '__main__.py').write_text(
                'from ._entry import main\nraise SystemExit(main())\n')
        (stage / 'main.py').write_text(
            'from _lunel_boot import *\n'
            'if __name__ == "__main__":\n'
            '    raise SystemExit(main())\n')
        (stage / 'BUILD.json').write_text(json.dumps({
            'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine(),
            'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        }, indent=2) + '\n')
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, output)
    print(f'Built {output}; use the same Python minor version and target platform.')


if __name__ == '__main__':
    main()
