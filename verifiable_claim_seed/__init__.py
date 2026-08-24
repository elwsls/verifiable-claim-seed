"""verifiable-claim-seed — machine-checkable claim contract + zero-dependency gate.

程序化使用入口：
  from verifiable_claim_seed import main, verify_claim
"""

from .verify_claim import main, verify_claim

__version__ = "1.3.0"
__all__ = ("main", "verify_claim", "__version__")
