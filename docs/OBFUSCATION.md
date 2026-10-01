# Protected distribution

Build on the same OS, CPU architecture, and Python minor version as the
deployment target. The build requires Node.js 22+, a C compiler, and Python
development headers. For Linux deployment, run the build in Linux.

```sh
python3 -m venv .venv-build
.venv-build/bin/pip install -r tools/obfuscation/requirements.txt -r requirements.txt
npm ci --prefix tools/obfuscation --ignore-scripts
.venv-build/bin/python tools/obfuscation/build.py
.venv-build/bin/pip install pytest pytest-asyncio
.venv-build/bin/python tools/obfuscation/verify.py dist/obfuscated
```

The output is `dist/obfuscated`. Python implementations are compiled into
native extension modules with debug symbols and docstrings removed. Only
minimal entrypoint launchers remain as Python source. JavaScript files and
inline scripts in both panels and subscription HTML are obfuscated using
control-flow flattening, injected dead code, hexadecimal identifiers, split
strings, and RC4-encoded string tables. API keys, property names, and module
exports retain their names to preserve public contracts. No source maps,
generated C files, tests, Git history, or build tools are distributed.

Install runtime dependencies from the output's `requirements.txt`, then run
`python main.py` from the output directory. Separate components still support
`python -m lunel_core`, `python -m lunel_console`, and `python -m lunel_worker`
from their respective directories. The existing Dockerfiles copy readable
source; use the protected distribution in a runtime image instead. Do not
copy the source checkout into an image intended to hide source code.

The build refuses to overwrite an existing output; use `--output <new-path>`
for subsequent builds. Keep the source checkout private if the objective is
to restrict access to readable implementations. This build cannot conceal
source already published on GitHub. Native code and browser scripts remain
reversible with sufficient effort. Obfuscation adds browser download and CPU
cost; it provides no protection for embedded secrets.
