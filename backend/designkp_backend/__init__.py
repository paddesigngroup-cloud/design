from __future__ import annotations

from pathlib import Path


_PACKAGE_ROOT = Path(__file__).resolve().parent
_SRC_PACKAGE = _PACKAGE_ROOT.parent / "src" / "designkp_backend"

__path__ = [str(_PACKAGE_ROOT)]
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))
