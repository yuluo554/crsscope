"""`python -m crsscope` 入口。

存在的理由：读者/CI 会敲 `python -m crsscope`，缺了它每条命令都报
`No module named crsscope.__main__`——而子命令入口本身是好的，这类缺陷只有"真敲一遍"才暴露。
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
