"""
L1 Knowledge OS — Domain-aware knowledge management.

Provides the Karpathy 4-operation model for knowledge:
  save(domain, topic, content) → Write to domain wiki
  load(domain, topic)          → Read from domain wiki
  search(domain, query)        → Vector search within domain
  derive(src, dst, query)      → Cross-domain synthesis with audit trail

Domains: game | market | personal
Each domain has isolated raw/ and wiki/ subdirectories.
"""

from .knowledge_os import KnowledgeOS, DomainError, CrossDomainLeakError

__all__ = ["KnowledgeOS", "DomainError", "CrossDomainLeakError"]
