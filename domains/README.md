# L1 Knowledge OS — Domains

## Structure

```
domains/
├── __init__.py          # KnowledgeOS class (Karpathy 4-op model)
├── knowledge_os.py      # Core implementation
├── game/
│   ├── .domain          # Domain metadata (name, description, allowed_squads)
│   ├── raw/             # Unprocessed ingestion source files
│   └── wiki/            # Promoted, canonical knowledge documents
├── market/
│   ├── .domain
│   ├── raw/
│   └── wiki/
└── personal/
    ├── .domain
    ├── raw/
    └── wiki/
```

## Domain Isolation Rules

1. **Squads only access domains explicitly listed in `.domain` `allowed_squads`**
2. **Vector search is scoped to a single domain collection** — no cross-domain search
3. **`derive()` is the ONLY cross-domain operation** — it requires explicit src/dst and leaves an audit trail
4. **promote.py `--domain` parameter routes artifacts to the correct domain wiki/**

## Karpathy 4-Operation Model

| Operation | Function | Isolation |
|-----------|----------|-----------|
| `save(domain, topic, content)` | Write to domain wiki/ | Single-domain |
| `load(domain, topic)` | Read from domain wiki/ | Single-domain |
| `search(domain, query)` | Vector search | Single-domain collection |
| `derive(src, dst, query)` | Cross-domain synthesis | Audited, explicit |
