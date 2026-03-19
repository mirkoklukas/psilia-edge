__version__ = "0.1.0"

import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.WARNING,
    handlers=[RichHandler(show_path=True)],
)
# 0.1.0 — pre-1.0 (in development)
# 1.0.0a1 — alpha
# 1.0.0b2 — beta
# 1.0.0 — stable release
# 1.0.0rc1 — release candidate
# 1.0.0.post1 — post-release
# 1.0.0.dev1 — dev release
