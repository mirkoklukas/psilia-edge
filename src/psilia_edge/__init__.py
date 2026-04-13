__version__ = "0.1.0"

import logging
from rich.logging import RichHandler

# Match ui.PADDING_LEFT (can't import from ui.py due to circular import)
_LOG_PADDING = 2

logging.basicConfig(
    level=logging.WARNING,
    format=f"{' ' * _LOG_PADDING}%(message)s",
    handlers=[
        RichHandler(
            show_time=False,
            show_level=False,
            show_path=False,
            markup=True,
        )
    ],
)
# 0.1.0 — pre-1.0 (in development)
# 1.0.0a1 — alpha
# 1.0.0b2 — beta
# 1.0.0 — stable release
# 1.0.0rc1 — release candidate
# 1.0.0.post1 — post-release
# 1.0.0.dev1 — dev release
