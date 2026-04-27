# Antigravity_MVP_Architecture 要件定義書 正本候補 v1.1

- **内部システム名**: NIM-Kinetic Meta-Agent MVP
- **対象リポジトリ**: `yosuku0/Antigravity_MVP_Architecture`
- **作成日**: 2026-04-26
- **文書ステータス**: CANONICAL / FROZEN (Approved by Human CEO)
- **作成目的**: 統合版v1.0を正本基盤とし、非機能要件・リスク分析・データスキーマの詳細を追加統合した、より堅牢な要件定義書

---

## 0. 文書ステータスと前提

### 0.1 本書の位置付け

本書は、`Antigravity_MVP_Architecture` リポジトリを対象とする統合要件定義書である。

本プロジェクトは、過去に並走していた以下の3つのプロジェクトを、1つの正本リポジトリに統合した結果として固定すべき要件を定義する。

1. `NIM-Kinetic Meta-Agent MVP`
2. `Karpathy-Method-AI-Agent`
3. `MY_LLMwiki-Brain_AI-Developer / wiki-blackboard-daemon`

本書は、これら3系統の思想・設計・実装成果を統合した「マスター要件」である。

ただし、以下のFROZEN文書・ADR・検証計画は、本書によって上書きされない。各局面では、それぞれの文書が局所的な最終権威となる。

- `doc/mvp_scope_freeze.md`: スコープ境界の最終権威
- `doc/job_lifecycle_spec.md`: JOB状態機械の最終権威
- `doc/adr/ADR-001-mvp-control-plane.md`: 制御プレーン設計の最終権威
- `doc/wbs-phase2.md`: Phase 2以降の作業分解の権威
- `doc/verification_plan.md`: 検証計画の権威
- `docs/JOB_SPEC.md`: JOB Schemaの権威
- `control-plane/constitutions/global.md`: 憲法的ルールの権威

### 0.2 正本化条件

本書は、Human CEO / Project Owner による承認を経て `CANONICAL` に昇格する。承認前は `CANONICAL-CANDIDATE` とし、正本候補として扱う。

### 0.3 変更禁止の不変則

以下はP0不変則である。

1. HITL Gate 1/2/3 は自動化で迂回しない。
2. `wiki/` への正規書き込みは `promote.py` を経由し、Gate 3承認後に限定する。
3. 正規のstatus writerは `wiki_daemon` とする。
4. `scripts/approve.py` はHuman CEO / operator の明示的承認操作を反映するためのHITL CLIであり、自律エージェントのstatus writerではない。
5. Brain / Developer / Researcher / CrewAI squads / LangGraph nodes は `status` を直接更新しない。
6. LangGraph は唯一の primary orchestrator とする。
7. CrewAI はLangGraph node内に閉じ込め、独立制御プレーン化しない。
8. `runtime/hermes/` は補助記憶であり、fact authorityではない。
9. `raw/` にAI生成物を逆流させない。
10. secret / API key をJOB、wiki、log、artifactに記録しない。

---

## 1. エグゼクティブサマリー

`Antigravity_MVP_Architecture` は、Slack / CLI からの自然言語依頼を `JOB` 契約へ変換し、LangGraphによる状態機械、LLM Router、CrewAI実行、Audit、HITL承認、`raw → wiki` 昇格、Hermes補助記憶、JSONLログ保存を一連のフローとして扱うAI開発メタシステムである。

目的は、AIが自律的に調査・設計・実装・レビュー・監査を進めつつも、知識正本を汚染せず、人間承認と監査証跡を維持できるローカルファーストな開発・知識運用基盤を構築することにある。

NVIDIA NIM / Blueprints は本プロジェクトの新規拡張要素である。ただし、現時点ではすべてをMVP実装済みとは扱わない。MVPではNIM-first routerとJSONL logging layerを中核にし、AI-Q / RAG / Data Flywheel本体はPhase F以降の段階的導入対象とする。

---

## 2. プロジェクト概要

### 2.1 プロジェクト名

- **リポジトリ名**: `Antigravity_MVP_Architecture`
- **内部システム名**: NIM-Kinetic Meta-Agent MVP
- **運用上の注意**: 「Antigravity」はユーザーの開発環境名でもある。本書ではリポジトリとしての `Antigravity_MVP_Architecture` を扱う。

### 2.2 目的

Slack / CLI からの依頼を起点に、以下の流れを安全に実行する。

```text
Natural Language Request
→ JOB生成
→ HITL Gate 1
→ wiki_daemon claim
→ LangGraph orchestration
→ plan / execute / review / audit
→ HITL Gate 2
→ promotion pending
→ HITL Gate 3
→ wiki promotion
→ Hermes reflection
→ JSONL logging
```

### 2.3 解決したい課題

| 課題 | 解決方針 |
|---|---|
| エージェント制御の散在 | LangGraphをprimary orchestratorに固定 |
| 知識正本の汚染 | `raw/`, `wiki/`, `work/`, `runtime/hermes/` を分離 |
| Brain / Developer の混線 | JOB契約とBlackboardを介して役割分離 |
| 状態不整合 | `wiki_daemon`、lock、JSONL、job filesで状態管理 |
| HITL省略 | Gate 1/2/3をP0不変則化 |
| NIM導入不安定性 | Hosted NIM-first、Ollama fallback |
| 改善ループ不在 | Data Flywheel-ready logging layerをMVP内で準備 |
| ドメイン横断汚染 | KnowledgeOSのdomain isolationと`derive()` audit |
| ロール境界の曖昧化 | Blackboard書き換え権限の役割別分離 |

### 2.4 非ゴール

- HITLなしの完全自動本番merge
- HITLなしのwiki自動昇格
- multi-tenant SaaS
- Self-hosted NIM本番運用
- Qdrant RAG / AI-Q Deep Research / Data Flywheel本体のMVP内全面導入
- ChatDev等の未確定上流への依存
- recursive job spawning
- nested LangGraph orchestration
- 第3ドメイン以上の同時並行運用
- **CLIツールの自律エージェント化（HITLなしの自動実行）**
- **CLIツールによるstatus / JOB / wikiの直接書き換え**
- **CLIツールをprimary orchestrator または LLM Router として統合**
- **Dockerを本番運用の唯一環境として固定**
- **genai-perfの本格導入（phased out、後継AIPerfはPhase H以降検討）**
- **ngc CLIをNIM API代替として使用**

---

## 3. 統合背景

本プロジェクトは、以下3つの先行プロジェクトを統合して成立した。

### 3.1 NIM-Kinetic Meta-Agent MVP

NVIDIA NIM-first router、HITL Gates、5-layer architecture、Data Flywheel logging、AI-Q / RAG / CrewAI / LangGraphの統合構想を提供した。

### 3.2 Karpathy-Method-AI-Agent

`raw → wiki` 昇格儀式、compiled knowledge、Brain / Developer役割分離、Hermes補助記憶、audit core、sidecar-first integration policyを提供した。

### 3.3 MY_LLMwiki-Brain_AI-Developer / wiki-blackboard-daemon

Blackboard通信、daemon-only status writer、fail-fast起動チェック、retry / freeze、illegal transition、Windows / PowerShell前提の運用思想を提供した。

---

## 4. 先行プロジェクトからの継承関係

| 先行プロジェクト | 継承内容 | 統合先 |
|---|---|---|
| NIM-Kinetic Meta-Agent MVP | 5-layer architecture、NIM-first router、HITL、CrewAI、JSONL logging | `apps/runtime/`, `apps/llm_router/`, `apps/crew/`, `logs/` |
| Karpathy-Method-AI-Agent | raw/wiki境界、promotion、Hermes、audit、Brain/Developer分離 | `domains/`, `scripts/promote.py`, `scripts/audit.py`, `runtime/hermes/` |
| MY_LLMwiki-Brain_AI-Developer | daemon、Blackboard、state machine、fail-fast | `apps/daemon/wiki_daemon.py`, `work/blackboard/`, `work/jobs/` |

---

## 5. 外部思想・Blueprintからの影響

### 5.1 Karpathy LLM Wiki

- `raw` を未加工sourceとし、`wiki` をcompiled knowledgeとする。
- LLMが毎回RAGで再発見するのではなく、重要知識をwikiへ蓄積・再利用する。
- `AGENTS.md` / schema / lint / log により、LLMの知識操作を制度化する。

本プロジェクトでの反映:

- `domains/<domain>/raw/`
- `domains/<domain>/wiki/`
- `scripts/promote.py`
- `scripts/audit.py`
- KnowledgeOS operations: `save`, `load`, `search`, `derive`

### 5.2 Rohit LLM Wiki v2

Rohit版の以下の概念は、MVPではなくPhase F以降 / P1+の拡張軸とする。

- memory lifecycle
- confidence scoring
- supersession
- retention / forgetting
- working / episodic / semantic / procedural memory tiers
- hybrid search
- typed knowledge graph
- contradiction resolution
- multi-agent sync
- shared / private scoping

### 5.3 NVIDIA Blueprints

| Blueprint / Element | 本プロジェクトでの扱い |
|---|---|
| NVIDIA NIM Chat Completion | MVP内のprimary provider候補。ただし現状はPartial / Degraded |
| NVIDIA AI-Q Blueprint | Research Node設計の参照。Deep ResearchはP1 |
| NVIDIA RAG Blueprint | Qdrant / embedding / rerankの将来参照。MVP外 |
| NVIDIA Data Flywheel Blueprint | MVPではJSONL logging layerのみ。評価・最適化ループはP2 |
| Safety / PII Guard Models | Future audit enhancement。現状はregex / static audit中心 |

### 5.4 選出GitHubリポジトリ統合戦略

本プロジェクトは、外部OSSリポジトリを「sidecar-first / read-only or staging-only」方針で段階的に統合する。以下の選出リポジトリは、各Phaseで統合を検討する候補である。

#### Sランク（即座統合・最優先）

| リポジトリ | 統合目的 | 統合先 | 対象CLI |
|---|---|---|---|
| `obra/superpowers` | L0 Workspace Scaffoldの拡張・代替。skills methodology基盤。 | `.agent_template/.agent/skills/`、`control-plane/constitutions/` | Claude, Codex, Cursor, Copilot CLI, OpenCode, Gemini |
| `sickn33/antigravity-awesome-skills` | SKILL.md playbookライブラリ。プロジェクト名「Antigravity」と一致。 | `.agent_template/.agent/skills/`（npx install） | Claude Code, Codex CLI, Gemini CLI, GitHub Copilot, Antigravity, Kiro, OpenCode |

#### Aランク（高親和・ロードマップ統合）

| リポジトリ | 統合目的 | 統合先 | 対象CLI |
|---|---|---|---|
| `rohitg00/agentmemory` | L1 Knowledge OSの検索・メモリ層強化。confidence scoring / lifecycle / hybrid search。 | `runtime/hermes/`またはL1 Knowledge OS検索層（MCP経由） | 全主要CLI（MCP対応） |
| `diegosouzapw/OmniRoute` | LLM Router設計の高度な参考。smart routing / cost-aware inference / rate limiting。 | `apps/llm_router/`の設計参照（TypeScript製のため直接統合不可） | 汎用 |
| `neilberkman/ccrider` | Hermes補助記憶強化。Claude Code/Codex CLIセッション検索・resume。 | `runtime/hermes/`（MCP経由） | Claude Code, Codex CLI |
| `hilash/cabinet` | Phase I外部OSS Pilot候補。AI-first knowledge base + startup OS。 | `integrations/cabinet/`（sidecar） | Claude Code CLI, Codex CLI |
| `agno-agi/pal` | L1 Knowledge OSの参照実装。raw→wikiコンパイルパイプライン。 | `domains/`のraw/wiki管理改善の参考 | Slack, Terminal |

#### Bランク（技術参考・部分統合）

| リポジトリ | 統合目的 | 統合先 |
|---|---|---|
| `Lanzelot1/claw-brain` | L0 Scaffold参考。`.claude/commands/` + raw/wikiパターン。 | `.agent_template/`コマンドテンプレート |
| `trkbt10/indexion` | L1 Knowledge OS参考。wiki + codegraph + KGF tokenizer。 | `domains/`ナレッジグラフ化検討材料 |
| `nousresearch/hermes-agent` | Hermes層の進化版。self-evolution（DSPy + GEPA）。 | Phase H以降で`runtime/hermes/`強化検討 |
| `garrytan/gbrain` | ナレッジグラフ・長期記憶の高度化。pgvector + hybrid search。 | Phase J以降検討 |

#### Cランク（思想・テンプレート参考）

| リポジトリ | 統合目的 |
|---|---|
| `Astro-Han/karpathy-llm-wiki` | Karpathy Wikiテンプレート。`domains/`テンプレート整備に活用。 |
| `msitarzewski/agency-agents` | 50種以上のエージェント定義参考。新規squad定義時のテンプレート。 |
| `midudev/autoskills` | Codex CLI専用スキルセット。Codex CLI導入時のskillsインポート先。 |

#### 既採用・必須（変更なし）

| リポジトリ | 役割 |
|---|---|
| `browser-use/browser-use` | Research Squadのweb調査機能 |
| `e2b-dev/e2b` | 3-tier Sandbox Tier 1 |
| `crewaiinc/crewai` | L3 Execution Runtime Squad実行 |
| `langchain-ai/langgraph` | Primary Orchestrator |
| `modelcontextprotocol/servers` | Phase G以降のMCP統合基盤 |

### 5.5 superpowers と antigravity-awesome-skills の使い分け

| | superpowers | antigravity-awesome-skills |
|---|---|---|
| **規模** | 168k stars、巨大エコシステム | 1.4k skills、コミュニティ駆動 |
| **思想** | 1-repo methodology | 分散ライブラリ |
| **統合性** | 高（インストールスクリプト完備） | 中（npx install） |
| **保守** | Claude公式もcontributor | コミュニティ主導 |
| **カスタマイズ** | 制限あり（methodology重視） | 自由（skills集積） |

**判断**: 両方並行して導入。superpowersを「methodology基盤」として、antigravity-awesome-skillsを「追加skillsライブラリ」として活用。superpowersの`AGENTS.md`・`CLAUDE.md`制度は、プロジェクトの`control-plane/constitutions/global.md`と統合可能。

### 5.6 OmniRoute に関する戦略的判断

OmniRoute（`diegosouzapw/OmniRoute`）は現状の`apps/llm_router/router.py`（Python製、NIM-first + Ollama fallback）を**置き換えるのではなく、参照・インスパイアする**立場が適切。

| 観点 | 現状の`router.py` | OmniRoute |
|---|---|---|
| **言語** | Python | TypeScript/Node.js |
| **スコープ** | ローカルファースト | Cloud-ready Gateway |
| **統合先** | LangGraph node内 | 独立サービス |
| **運用** | `.env`内API key管理 | Dashboard, DB, Docker |
| **制約** | max 2 provider switches | Unlimited routing rules |

**判断**: OmniRouteの**smart routingアルゴリズム・rate limiting設計・observabilityパターン**を`router.py`のPhase H改善に取り入れる。実コードの統合は見送り、設計思想の参照とする。

### 5.7 NVIDIA CLIツール選出

NVIDIAが提供するCLIツールの中から、Docker運用前提でプロジェクトに採用可能なツールを選出する。

| ツール | 採用判断 | 理由 | 統合Phase |
|---|---|---|---|
| **nvidia-ctk** | **Sランク：採用** | Dockerコンテナ内でGPUを使用するための必須ツール。`nvidia-ctk runtime configure --runtime=docker` でDockerランタイムを設定し、`docker run --gpus all` でGPUアクセスを提供。Docker運用前提では不可欠。 | F |
| **nvidia-smi** | **Aランク：採用** | GPU監視・管理の標準ツール。利用率、メモリ、温度、電力をリアルタイム監視。Docker内でもnvidia-ctk経由で使用可能。観測性（NFR-A050）に貢献。ただし、これはGPUドライバー付属ツールであり「導入」より「利用」。 | F |
| **ngc CLI** | **Bランク：選定的採用** | NGCレジストリ（nvcr.io）へのアクセス。NVIDIAコンテナイメージ・モデル・リソースのpullに使用。Self-hosted NIMはRejectedだが、nvcr.ioからのコンテナpull（Triton SDK等）は有用。`ngc registry image info/list`、`docker login nvcr.io`等。 | G〜H |
| **genai-perf** | **非推奨・見送り** | 公式により "GenAI-Perf is being phased out. We are no longer actively developing new features for GenAI-Perf." と宣言済み。後継の **AIPerf** はPhase H以降でSelf-hosted NIM/Triton検討時に再評価。現状はRejected。 | — |

#### nvidia-ctk の Docker統合パス

```bash
# NVIDIA Container Toolkit インストール（Ubuntu/WSL2）
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |   sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |   sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |   sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# Docker runtime 設定
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 検証
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

#### Docker運用の限定範囲

Dockerは以下の限定範囲で採用する。Windows + PowerShellは主環境を維持し、DockerはWSL2 backendまたは開発環境標準化のオプションとして位置付ける。

1. **開発環境標準化**: 開発者間の環境差異を減らすためのコンテナ化（選定的）
2. **GPUワークロード実行**: Self-hosted NIM/TritonはRejectedだが、nvcr.ioからのコンテナ実行（benchmark等）は可能
3. **CI/CD統合**: GitHub Actions等でのコンテナベーステスト（将来検討）
4. **本番運用**: Docker単独での本番運用は非ゴール。Windows + PowerShellを主環境とする

---

## 6. 現在地

### 6.1 実装ステータス概要

| Layer / Feature | Status | Notes |
|---|---|---|
| L0 Workspace Scaffold | Implemented / Partial | 標準構成・憲法文書 |
| L1 Knowledge OS | Implemented | domain isolation、raw/wiki、derive |
| L2 Coordination Daemon | Implemented | `wiki_daemon`、lock、state management |
| L3 Execution Runtime | Partially Implemented | LangGraph / CrewAI / Router / Sandbox |
| HITL Gates | Implemented | Gate 1/2/3 |
| 3-tier Sandbox | Implemented | e2b / local venv / skip |
| NVIDIA NIM | Partial / Degraded | 401課題によりOllama fallback運用 |
| Qdrant RAG | Deferred | P1以降 |
| AI-Q Deep Research | Deferred | P1以降 |
| Data Flywheel loop | Deferred | MVPはlogging layerのみ |
| **nvidia-ctk** | **Not Implemented** | **Phase FでDocker GPU運用基盤として導入予定** |
| **nvidia-smi** | **Operational** | **GPUドライバー付属。Docker内でも利用可** |
| **ngc CLI** | **Not Implemented** | **Phase G以降、nvcr.ioアクセス用に選定的導入予定** |
| **Docker（WSL2 backend）** | **Not Implemented** | **Phase Fで開発環境標準化のオプションとして検討** |

### 6.2 Phase E時点の検証状況

- `pytest tests/`: 43/43 passed と記録されている。
- `scripts/scope_guard.py .`: PASS と記録されている。
- Gate 1/2/3を含む手動E2Eはリリースゲート条件として維持する。

注記: 本書作成時点では、これらは既存報告に基づく記録であり、本書作成処理自体ではテストを再実行していない。

### 6.3 既知の制限事項

| 項目 | 内容 | 対応方針 |
|---|---|---|
| NIM via CrewAI/LiteLLM | 401 エラーが発生 | Workaround: Ollama を実行ドライバに固定。P1 で `langchain-nvidia-ai-endpoints` への移行 |
| LangGraph checkpoint resume | 自動再開未実装 | MVP では daemon クラッシュ時 `FAILED` 遷移、operator が新規 JOB に clone。Resume は P1 |
| `max_workers=3` 固定 | squad 数に応じた動的化なし | Phase F 以降で検討 |
| 並列実行時の一時 artifact | `{job_id}_{squad_name}.md` の自動cleanup未整備 | Phase F 以降 |
| NIM vs Ollama benchmark | 未実施 | Phase F 以降 |
| Slack ingress | コードはあるが、現状 CLI 主運用 | Slack を本格利用するかは Phase F 以降に再評価 |
| **CLIツール統合の初期制限** | 各CLIの操作ログ統一`cli_operations.jsonl`のschema設計未確定 | Phase Fで`logs/cli_operations.jsonl` schemaを確定・実装 |
| **CLI憲法文書整備** | `CLAUDE.md`/`CODEX.md`/`GEMINI.md`/`KIMI.md`の作成未着手 | Phase Fで各CLI憲法文書を整備。`control-plane/constitutions/`との整合性確認 |
| **CLI操作の範囲境界** | CLIツールが`work/`外のファイル（`.env`等）を誤って編集するリスク | Phase Fで`scripts/scope_guard.py`にCLI操作範囲チェックを追加 |
| **superpowers導入判断** | methodology基盤として導入するか、skillsライブラリのみに留めるか未決定 | Phase Fでsuperpowers + antigravity-awesome-skillsの導入判断 |

---

## 7. ステークホルダー

| 主体 | 役割 | 権限 |
|---|---|---|
| Human CEO / Higurashi | 最終意思決定者 | HITL承認、ADR承認、スコープ変更 |
| wiki_daemon | 状態管理者 | 正規status writer、lock、claim、fail-fast |
| LangGraph | Primary orchestrator | JOB実行フロー制御 |
| Brain Agent | 計画者 | objective、plan、review feedback |
| Developer / Executor | 実行者 | artifact生成、sandbox実行 |
| Research Agent | 調査者 | evidence生成、research report |
| Audit Agent / Script | 監査者 | secret scan、domain check、syntax check |
| Hermes | 補助記憶 | wiki変更要約のappend-only反映 |
| System Operator | 運用者 | env、secret、障害対応、manual E2E |
| **Claude Code** | Brain Agent補助 | 高次設計・計画・レビュー・HITL操作支援。blackboard経由で介入。 |
| **Codex CLI** | Developer / Executor補助 | 実装・コーディング・sandbox実行支援。artifact生成支援。 |
| **GitHub Copilot CLI** | Developer補助 | コード補完・リファクタリング・軽微な修正支援。 |
| **Gemini CLI** | Research Agent補助 | 調査・検索・Evidence生成・Web検索支援。 |
| **Kimi Code** | KnowledgeOS / Hermes補助 | 知識管理・ドキュメント処理・メモリ強化。derive / save / load支援。 |
| **OpenAI Wrapper** | LLM Router統合 / 汎用fallback | OpenAI API互換の汎用provider。Router fallback候補。 |

---

## 8. 用語定義

| 用語 | 定義 |
|---|---|
| JOB | `work/jobs/` に置かれるMarkdown/YAML形式の作業契約 |
| HITL | Human-In-The-Loop。人間承認を挟む安全機構 |
| Gate 1 | JOB内容の承認 |
| Gate 2 | Artifact / 実行結果の承認 |
| Gate 3 | wiki昇格の承認 |
| raw | 未加工source。AI生成物の逆流は禁止 |
| wiki | compiled knowledgeの正本 |
| work | operational state、JOB、lock、blackboard |
| Hermes | 補助記憶。fact authorityではない |
| Promotion | 承認済みartifactをwikiへ昇格する操作 |
| Blackboard | Agent間の中間成果物・feedback共有領域 |
| Canonical | 正本。承認済みの参照基準 |
| Deferred | MVP外。将来フェーズで検討 |
| Rejected | 明示的に対象外 |

---

## 9. アーキテクチャ要件

### A-ARC-001: 5レイヤー統合構造

- **Description**: L0 Workspace Scaffold、L1 Knowledge OS、L2 Coordination Daemon、L3 Execution Runtime、Content Domainの5層を維持する。
- **Origin**: NIM-Kinetic
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - `apps/`、`domains/`、`work/`、`docs/`、`runtime/` が役割分離されている。
  - 制御プレーンとデータプレーンが混線しない。
- **Related Files**: `apps/`、`domains/`、`work/`、`docs/`、`runtime/`
- **Related Tests**: scope guard / architecture review

### A-ARC-002: LangGraph Primary Orchestrator

- **Description**: LangGraphを唯一のprimary orchestratorとし、CrewAIはLangGraph node内に閉じ込める。
- **Origin**: ADR-001 / NIM-Kinetic
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - CrewAIが独立制御プレーンとしてJOB状態を変更しない。
  - LangGraphのネスト深度は1を超えない。
- **Related Files**: `apps/runtime/graph.py`、`apps/crew/`
- **Related Tests**: T007, T008, T015

### A-ARC-003: Control Plane / Data Plane分離

- **Description**: JOB、lock、blackboard、logsをControl Plane、domains/wiki/raw/scripts/appsをData Planeとして分離する。
- **Origin**: Karpathy / MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - JOB stateは`work/jobs/`とdaemon管理下で扱う。
  - wikiへの反映はpromotion経由に限定される。
- **Related Files**: `work/`、`domains/`、`scripts/promote.py`
- **Related Tests**: T001, T006, T009

### A-ARC-004: Blackboardパターン

- **Description**: BrainとDeveloper/ExecutorはLangGraph stateをblackboardとして通信する。中間結果は`work/blackboard/feedback/{artifact_stem}.json`に書き出す。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - 書き換えてよいフィールドを役割ごとに限定する。
  - 各役割が許可外フィールドを書き換えた場合、auditが検知する。
- **Related Files**: `work/blackboard/`、`apps/runtime/nodes/`
- **Related Tests**: T007, T015

#### Blackboard書き換え権限表

| 役割 | 書き換え可フィールド | 書き換え不可フィールド |
|---|---|---|
| daemon | `status`、`daemon_state.json`、`logs/daemon.jsonl` | objective、artifact 内容 |
| plan_executor (Brain) | `planned_objective` | `status` |
| run_executor (Executor) | `artifact_path`、`result` | `status` |
| brain_review | `review_feedback`、`review_count` | `status`、`audit_result` |
| audit | `audit_result` | `status` |
| promote | `wiki/` ページ追加 | `status` 直接（promote 経由のみ） |

---

## 10. 機能要件

### A-FR-010: JOB契約

- **Description**: JOBは唯一の作業契約であり、自然言語依頼は最終的に `work/jobs/JOB-*.md` へ変換される。
- **Origin**: NIM-Kinetic / MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - JOBに `job_id`、`type`、`domain`、`status`、`priority`、`objective` が含まれる。
  - JOBは`docs/JOB_SPEC.md`に準拠する。
- **Related Files**: `docs/JOB_SPEC.md`、`work/jobs/`
- **Related Tests**: T001, T002

### A-FR-020: wiki_daemonによる状態監視

- **Description**: `wiki_daemon` は `work/jobs/` を監視し、claim、lock、state transition、fail-fast、JSONL記録を行う。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - 規約外ファイルを無視する。
  - 不正遷移を検知して停止またはskipする。
  - stale lockを適切に処理する。
- **Related Files**: `apps/daemon/wiki_daemon.py`
- **Related Tests**: T001, T002, T011

### A-FR-030: LangGraph実行フロー

- **Description**: JOBを読み込み、plan、execute、review、auditまでの実行フローをStateGraphで制御する。
- **Origin**: NIM-Kinetic
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - Gate 1/2で中断し、人間承認後に次段階へ進む（Gate 3は昇格時に適用）。
  - audit失敗時に終了し、後続の昇格プロセスへ進まない。
- **Related Files**: `apps/runtime/graph.py`
- **Related Tests**: T007, T008, T009, T015

#### グラフ構造

```
load_job → squad_router → plan_executor → run_executor → brain_review
                                                              ↓
                                                          (rejected, count<3)
                                                              ↓
                                                          plan_executor
                                                              ↓
                                                         (approved or count>=3)
                                                              ↓
                                                         audit → END
                                                              ↓
                                                          (failed) → END
```

詳細状態機械は `doc/job_lifecycle_spec.md` を権威とする（CREATED / APPROVED_GATE_1 / CLAIMED / ROUTED / EXECUTING / AUDIT_PASSED / AUDIT_FAILED / GATE_2_REJECTED / APPROVED_GATE_2 / PROMOTION_PENDING / APPROVED_GATE_3 / PROMOTED / FAILED / CANCELLED）。

#### 実行境界 (Execution Boundary)

LangGraphの実行範囲は **audit** までであり、wikiへの昇格（promotion）は含まない。

- LangGraphはaudit完了後に終了し、`END`へと遷移する。
- LangGraphはartifactのステージング（staging）を行わない。
- LangGraphはwikiコンテンツの昇格（promotion）を行わない。
- wikiへの正本書き込みは `scripts/promote.py --mode execute` を介してのみ実行される。

#### 昇格フロー (Promotion Flow)

昇格はLangGraphの外側で、人間による承認（Gate 2/3）をトリガーとして `wiki_daemon` および `promote.py` によって制御される。

```text
audit_passed
→ Gate 2 Slack/CLI承認
→ approved_gate_2
→ wiki_daemon が `scripts/promote.py --mode stage` を実行
→ promotion_pending
→ Gate 3 CLI承認
→ approved_gate_3
→ wiki_daemon が `scripts/promote.py --mode execute` を実行
→ promoted
```

### A-FR-040: Brain / Developer分離

- **Description**: Brainは計画とレビュー、Developerは実装とartifact生成を担い、statusを直接変更しない。
- **Origin**: Karpathy-Method
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - Brain / Developer はBlackboardまたはpayloadを介して通信する。
  - status変更はdaemonまたはHITL承認操作に限定される。
- **Related Files**: `apps/runtime/nodes/plan_executor.py`、`apps/runtime/nodes/run_executor.py`、`work/blackboard/`
- **Related Tests**: T007, T015

### A-FR-050: CrewAI Squad実行

- **Description**: Coding / Research / Review squadsをLangGraph node内で呼び出し、artifactを生成する。
- **Origin**: NIM-Kinetic
- **Priority**: P1
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - squad出力はartifactとして保存される。
  - squadはstatusを直接更新しない。
- **Related Files**: `apps/crew/`、`apps/crew/squad_executor.py`
- **Related Tests**: squad integration tests / T015

### A-FR-060: LLM RouterとFallback

- **Description**: NIM-firstのLLM Routerを提供し、失敗時はOllama等へfallbackする。
- **Origin**: NIM-Kinetic
- **Priority**: P1
- **Status**: Partially Implemented / Degraded
- **Acceptance Criteria**:
  - 有効なNIM API keyがある場合はNIMを優先選択する。
  - NIM失敗時はprovider-switch budget内でfallbackする。
  - provider-switchは最大2回までとする。
  - per-node retryは最大3回、per-job total retryは最大5回。
  - fallbackトリガは技術的失敗（HTTP timeout / 5xx / connection reset / DNS fail）のみ。「品質が悪い」「拒否された」はfallback対象外。
  - `routing_config.yaml` はruntime read-only（dynamic model_policy loading禁止）。
- **Related Files**: `apps/llm_router/router.py`、`apps/llm_router/complexity_scorer.py`
- **Related Tests**: T004, T005

#### LLM Router Layer

- **Primary**: NVIDIA NIM（OpenAI 互換 chat completion、`https://integrate.api.nvidia.com/v1/chat/completions`）
- **Fallback**: Ollama（local、qwen2.5:7b / qwen2.5-coder:7b / gemma2:27b）
- **Optional**: Claude / Gemini / OpenAI / Kimi（既存 paid providers）
- **制約**: provider-switch は最大2回（`MAX_PROVIDER_SWITCHES=2`）、超過で `ProviderBudgetExhausted` → JOB FAILED
- **制約**: per-node retry max 3、per-job total retry max 5
- **制約**: `routing_config.yaml` はruntime read-only

### A-FR-070: KnowledgeOS / Domain Isolation

- **Description**: `game`、`market`、`personal` 等のdomainを分離し、cross-domainアクセスは `derive()` に限定する。
- **Origin**: Karpathy / NIM-Kinetic
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - direct cross-domain wiki linkをauditで検知する。
  - `derive()` はaudit traceを残す。
  - squadは`.domain` `allowed_squads`に列挙されたドメインしか触れない（`SquadPermissionError`）。
- **Related Files**: `domains/knowledge_os.py`、`scripts/audit.py`
- **Related Tests**: domain isolation tests / T006

#### 4-op Model

- `save(domain, topic, content)`
- `load(domain, topic)`
- `search(domain, query)`
- `derive(src, dst, query)`

### A-FR-080: Audit

- **Description**: Secret scan、syntax check、domain leak checkを実行する。
- **Origin**: Karpathy-Method
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - secret pattern検出時にFAILする。
  - audit FAIL時にpromotionへ進まない。
  - AUDIT_FAILEDとGATE_2_REJECTEDは別状態として区別し、別JSONLイベント・別メトリクスを持つ。
  - reworkはAUDIT_FAILEDとGATE_2_REJECTEDから各々最大2回までEXECUTINGに戻せる。
- **Related Files**: `scripts/audit.py`
- **Related Tests**: T006

### A-FR-090: Promotion

- **Description**: Gate 3承認後、`promote.py` によって承認済みartifactを `wiki/` へ昇格する。
- **Origin**: Karpathy-Method
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - `approved_gate_3_by` なしにwiki書き込みをしない。
  - `wiki/` 直接書き込みを正規フローとして扱わない。
  - `promote.py --domain {game|market|personal}` でdomain wikiに書き込む。
  - `wiki/` 書き込みはPROMOTED状態でのみ発生する。それ以前の状態で`wiki/`が変化した場合はsecurity incidentとみなす。
- **Related Files**: `scripts/promote.py`
- **Related Tests**: T009

### A-FR-100: Hermes Reflection

- **Description**: promotion後、Hermesに変更要約をappend-onlyで反映する。
- **Origin**: Karpathy-Method
- **Priority**: P1
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - Hermesは補助記憶であり、fact authorityとして扱われない。
  - `hermes_reflect.py` はPROMOTED後にのみ実行され、`runtime/hermes/memory.md`にappend-only。
- **Related Files**: `scripts/hermes_reflect.py`、`runtime/hermes/`
- **Related Tests**: T012

### A-FR-110: Parallel Execution

- **Description**: `parallel: true` のJOBでは、最大3 workerでsquad実行を並列化する。
- **Origin**: NIM-Kinetic Phase E
- **Priority**: P1
- **Status**: Implemented
- **Acceptance Criteria**:
  - artifact pathがJOB / squad単位で隔離される。
  - max_workersは初期値3とする。
  - 結果統合はsquad定義順で行う（順序保証）。
- **Related Files**: `apps/crew/squad_executor.py`
- **Related Tests**: parallel execution tests

### A-FR-120: Cancel

- **Description**: 処理中または待機中のJOBを取り消す。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - cancelはterminal状態（PROMOTED / FAILED / CANCELLED）以外から可能。
  - PROMOTION_PENDING / APPROVED_GATE_3 でcancelされた場合、`work/artifacts/staging/JOB-###/` を削除する。
  - それ以前の状態でcancelされた場合、stagingは無いので削除なし。
  - cancel後lockは除去、JOB statusは`cancelled`、working dirはdebug用に温存。
- **Related Files**: `scripts/cancel.py`
- **Related Tests**: manual E2E

### A-FR-130: Workspace Scaffold（L0 / Karpathy由来）

- **Description**: エージェントテンプレートと憲法文書によるL0層の整備。
- **Origin**: Karpathy
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - `.agent_template/.agent/` に context.md / rules.md / memory.md の loading order を持つ。
  - `control-plane/constitutions/global.md` を全agentが読むconstitutional rulesとする。
  - `scripts/init_project.py` でtemplateから新規プロジェクトをscaffoldできる。
- **Related Files**: `.agent_template/`、`control-plane/constitutions/global.md`
- **Related Tests**: N/A

### A-FR-140: YAML検証 / 状態遷移

- **Description**: `wiki_daemon` はfrontmatterを検証し、不正遷移をfail-fastで処理する。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - 必須キー欠落・YAMLパース失敗時に`validation_error`をJSONLに記録し、JOBファイルを書き換えない。
  - 禁止遷移を検知した場合はJOBファイルを書き換えず`illegal_transition`をJSONLに記録する。
  - `daemon_state.json` の `last_known_status` を遷移判定のground truthとし、JOB fileのstatusと矛盾する場合は`last_known_status`を信頼する。
  - invalid YAML / illegal transitionでJOBを自動修復しない（fail-fast / skip+log）。
- **Related Files**: `apps/daemon/wiki_daemon.py`
- **Related Tests**: T001, T002, T011

### A-FR-150: 起動時整合性チェック

- **Description**: daemon起動時の整合性チェックとfail-fast動作。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - state file不在 + 実JOB 0件 → 空stateで起動可。
  - state file不在 + 実JOB 1件以上 → fail-fastで停止する。operatorが手動判断するまで再起動しない。
  - state file破損（JSON parse不能）→ fail-fast。
  - `.tmp` のみ残存 → `.tmp` を削除した上で再度判定。
  - 起動完了後、`logs/daemon.jsonl` に `startup` イベントを記録する。
- **Related Files**: `apps/daemon/wiki_daemon.py`
- **Related Tests**: T001, T011

### A-FR-160: Atomic Lock / Stale Recovery

- **Description**: atomic lockによる排他制御とstale lock回収。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - lock取得は`O_CREAT | O_EXCL`のみを用い、失敗時は競合を意味する。
  - lock fileにはISO timestamp（`YYYYMMDDHHMMSS`）とPIDを書く。
  - lockのageが10分超かつPIDがdeadの場合のみstaleと判定する。
  - 生存PIDのロックは年齢に関わらず奪わない。
  - stale lockは`work/locks/archived/{job_id}_{ts}.lock`に退避してから再取得する。
  - stale回収はexecutionを再開しない。`executing/routed`は`FAILED`、`claimed`は`approved_gate_1`に戻す。承認メタデータは `approved_by` を使用。
- **Related Files**: `apps/daemon/wiki_daemon.py`
- **Related Tests**: T001, T011

### A-FR-170: CLIツール統合 — 役割分担

- **Description**: 各CLIツールをプロジェクトの役割体系に整合させ、役割分担型で導入する。各CLIは「人間が操作する介助ツール」として位置付け、自律エージェントとしてのstatus変更は禁止する。
- **Origin**: CLI統合戦略
- **Priority**: P0
- **Status**: Policy / Partially Implemented
- **Acceptance Criteria**:
  - Claude Code: Brain Agent補助として、高次設計・計画・レビュー・HITL操作支援に使用。blackboard経由で介入。`status`直接書き換え禁止。
  - Codex CLI: Developer / Executor補助として、実装・コーディング・sandbox実行支援に使用。artifact生成支援。`status`直接書き換え禁止。
  - GitHub Copilot CLI: Developer補助として、コード補完・リファクタリング・軽微な修正支援に使用。`status`直接書き換え禁止。
  - Gemini CLI: Research Agent補助として、調査・検索・Evidence生成・Web検索支援に使用。`status`直接書き換え禁止。
  - Kimi Code: KnowledgeOS / Hermes補助として、知識管理・ドキュメント処理・メモリ強化に使用。`derive` / `save` / `load`支援。`status`直接書き換え禁止。
  - OpenAI Wrapper: LLM Router統合 / 汎用fallbackとして使用。OpenAI API互換の汎用provider。Router fallback候補。
  - いずれのCLIも、HITLなしで自動的にGateを通過したり、JOBを承認したり、wikiを昇格させたりしない。
- **Related Files**: `.agent_template/`、`control-plane/constitutions/`、`docs/operations/cli_integration_guide.md`
- **Related Tests**: manual E2E / scope guard

### A-FR-180: Claude Code統合

- **Description**: Claude CodeをBrain Agent補助として統合。計画・設計・レビューフェーズでHuman CEO / Operatorが使用。
- **Origin**: superpowers / antigravity-awesome-skills
- **Priority**: P1
- **Status**: Policy / Partially Implemented
- **Acceptance Criteria**:
  - `.claude/CLAUDE.md`（または`CLAUDE.md`）がプロジェクトルートに配置され、プロジェクトの制約・ルール・HITL方針を記載する。
  - Claude Codeは`work/blackboard/`の読み取り・書き込みが可能（所定のフィールドのみ）。
  - Claude Codeによる`wiki/`直接編集は禁止。`scripts/audit.py`の実行は禁止。
  - Claude Codeの操作ログは`logs/cli_operations.jsonl`に記録（操作者、操作内容、タイムスタンプ）。
- **Related Files**: `CLAUDE.md`、`work/blackboard/`、`logs/cli_operations.jsonl`
- **Related Tests**: scope guard / manual verification

### A-FR-190: Codex CLI統合

- **Description**: Codex CLIをDeveloper / Executor補助として統合。実装フェーズで使用。
- **Origin**: superpowers / midudev/autoskills
- **Priority**: P1
- **Status**: Policy / Partially Implemented
- **Acceptance Criteria**:
  - `.codex/CODEX.md`（または`CODEX.md`）がプロジェクトルートに配置され、コーディング規約・sandbox実行規則を記載する。
  - Codex CLIは`work/artifacts/`の生成・編集が可能。`wiki/`直接編集は禁止。
  - Codex CLIによる`scripts/audit.py`編集は禁止。`AGENTS.md`編集は禁止。
  - Codex CLIの操作ログは`logs/cli_operations.jsonl`に記録。
  - `codex`コマンドによるsandbox実行は、`utils/safe_subprocess.py`経由に限定する。
- **Related Files**: `CODEX.md`、`work/artifacts/`、`logs/cli_operations.jsonl`、`utils/safe_subprocess.py`
- **Related Tests**: scope guard / sandbox tests

### A-FR-200: GitHub Copilot CLI統合

- **Description**: GitHub Copilot CLIをDeveloper補助として統合。コード補完・リファクタリング支援。
- **Origin**: superpowers
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - Copilot CLIはコード補完・リファクタリング支援に限定。新規ファイル生成はCodex CLIまたはCrewAI Squadが担当。
  - Copilot CLIはLLM Routerとして機能しない（A-FR-060のRouter layerとは独立）。
  - Copilot CLIのsuggestionはaudit対象外とするが、最終commit前には`scripts/audit.py`を通す。
  - `.github/copilot/`にプロジェクト固有のinstructionを配置可能。
- **Related Files**: `.github/copilot/`、`scripts/audit.py`
- **Related Tests**: audit tests

### A-FR-205: Gemini CLI統合

- **Description**: Gemini CLIをResearch Agent補助として統合。調査・検索・Evidence生成支援。
- **Origin**: superpowers
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - Gemini CLIはResearch Squadの補助として使用。Web検索・資料収集・Evidenceドラフト生成。
  - Gemini CLIによるEvidenceは`work/blackboard/evidence/`に一時保存。最終EvidenceはBrain Agentのレビューを経て確定。
  - Gemini CLIは`wiki/`直接編集禁止。`status`直接書き換え禁止。
  - `.gemini/GEMINI.md`（または`GEMINI.md`）がプロジェクトルートに配置され、調査方針を記載する。
- **Related Files**: `GEMINI.md`、`work/blackboard/evidence/`、`apps/crew/squads/research_squad/`
- **Related Tests**: research squad tests

### A-FR-208: Kimi Code統合

- **Description**: Kimi CodeをKnowledgeOS / Hermes補助として統合。知識管理・ドキュメント処理・メモリ強化。
- **Origin**: superpowers
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - Kimi Codeは`domains/`の読み取り・`runtime/hermes/`の書き込みが可能。
  - Kimi Codeによる`wiki/`直接編集は禁止（promote.py経由のみ）。
  - Kimi CodeはKnowledgeOSの`derive()`支援に使用。cross-domainアクセス時はaudit traceを残す。
  - Kimi Codeの操作ログは`logs/cli_operations.jsonl`に記録。
  - `.kiwi/KIMI.md`（または`KIMI.md`）がプロジェクトルートに配置され、知識管理方針を記載する。
- **Related Files**: `KIMI.md`、`domains/`、`runtime/hermes/`、`logs/cli_operations.jsonl`
- **Related Tests**: domain isolation tests / hermes tests

### A-FR-210: OpenAI Wrapper統合

- **Description**: OpenAI Wrapper（oapi / 汎用OpenAI互換ツール）をLLM Routerのfallback provider候補として統合。
- **Origin**: CLI統合戦略
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - OpenAI Wrapperは`apps/llm_router/router.py`のfallback providerリストに含まれる。
  - `.env`に`OPENAI_API_KEY`が設定されている場合、Ollama fallbackの前段または並列候補として使用可能。
  - OpenAI Wrapperは独立したCLI操作として使用する場合、Brain/Developer補助としての役割分担を遵守する。
  - OpenAI Wrapperによる直接プロンプト実行は`logs/model_calls.jsonl`に記録。
- **Related Files**: `apps/llm_router/router.py`、`.env.example`、`logs/model_calls.jsonl`
- **Related Tests**: T004, T005

---

## 11. 非機能要件

### 11.1 実行環境

#### A-NFR-001: 実行環境

- **Description**: Windows 10/11 + PowerShellを主環境とし、WSL2 / Linux互換を維持する。
- **Priority**: P0
- **Status**: Implemented / Operational
- **Acceptance Criteria**:
  - PowerShellから主要scriptを実行できる。
  - Python 3.12+で依存関係が解決できる。
  - Python 3.14でも互換維持（Phase Eで`requirements.txt`緩和済）。
  - WSL2 / Linuxでも動作可能。`os.O_EXCL`が利用可能なfsであれば動く。
- **Related Files**: `requirements.txt`、`.env.example`、scripts
- **Related Tests**: manual verification

### 11.2 性能

#### A-NFR-010: 性能目標

| ID | 指標 | 目標 | 備考 |
|---|---|---|---|
| NFR-A10 | JOB生成応答（CLI） | 10秒以内 | |
| NFR-A11 | wiki_daemonのJOB検知 | 5秒以内 | |
| NFR-A12 | 1 JOB処理（LLM応答待ち除く） | 60秒以内 | |
| NFR-A13 | shallow research（P1） | 60秒以内 | Phase G以降 |
| NFR-A14 | deep research（P1） | 10分以内 | Phase G以降 |
| NFR-A15 | RAG検索 p95（P1） | 2秒以内 | Qdrant導入後 |
| NFR-A16 | LLM router fallback切替 | 1回失敗後30秒以内 | |
| NFR-A17 | 同時JOB数 | MVPは3件 | max_workers=3に対応 |

- **Priority**: P1
- **Status**: Policy / Partially Measured
- **Related Tests**: Phase F benchmark tests

### 11.3 可用性

#### A-NFR-020: 可用性要件

- **Description**: 外部サービス障害時も継続実行可能な可用性を確保する。
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - NFR-A20: NIM障害時、Ollama fallbackで実行を継続できる。
  - NFR-A21: LangGraph中断時、SQLite checkpointは保存される（自動resumeはP1）。
  - NFR-A22: Qdrant等のRAG障害時、Evidence不足としてWARNしつつ実行は継続できる（P1）。
  - NFR-A23: Slack障害時、CLIで全操作可能。
- **Related Files**: `apps/llm_router/router.py`、`apps/runtime/graph.py`
- **Related Tests**: T004, T005, manual E2E

### 11.4 信頼性

#### A-NFR-030: 信頼性要件

- **Description**: atomic write、lock、fail-fast、stale lock recoveryにより状態破損を最小化する。
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - NFR-A30: 通常運転中のtaskエラーはログを残して継続できる。
  - NFR-A31: 初期化フェーズの致命的不整合はfail-fastで停止する。
  - NFR-A32: state fileの部分書き込みは禁止（atomic write `tmp → fsync → rename`）。
  - NFR-A33: lockは10分超かつdead PIDのみstale認定し、生存PIDは奪わない。
  - state file破損時に安全側で停止する。
  - duplicate claimを防止する。
- **Related Files**: `apps/daemon/wiki_daemon.py`、`utils/atomic_io.py`
- **Related Tests**: T001, T011

### 11.5 セキュリティ

#### A-NFR-040: セキュリティ要件

- **Description**: secret管理、危険subprocess検知、未承認promotion防止を実施する。
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - NFR-A40: secretは`.env`のみ。コード/JOB/wiki/logへの混入禁止。
  - NFR-A41: PII/secret detectionはMVPではregexを使う（NIM safety modelはP1）。
  - NFR-A42: prompt injection対策としてretrieved contextは明示区切りでsystem instructionと分離（P1）。
  - NFR-A43: 本番反映/wiki昇格/外部公開はHITL必須。
  - NFR-A44: audit trailとして全JOB/model call/承認/promoteをJSONLに記録。
  - NFR-A45: subprocessは`utils/safe_subprocess.py`経由のみ。`scripts/scope_guard.py`の静的解析でブロックする。
  - `.env` 以外にsecretを置かない。
  - `scope_guard.py` が危険操作を検知する。
- **Related Files**: `.env.example`、`scripts/scope_guard.py`、`scripts/audit.py`、`utils/safe_subprocess.py`
- **Related Tests**: scope guard tests

### 11.6 観測性

#### A-NFR-050: 観測性要件

- **Description**: structured loggingとmetrics収集を統一的に実施する。GPUリソース監視も含む。
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - NFR-A50: structured loggingはJSONL形式で統一。
  - NFR-A51: trace idとしてJOB IDを全ログに付与。
  - NFR-A52: metrics: latency / tokens / error rate / fallback count / cost estimate。
  - NFR-A53: dashboard（Grafana / LangSmith / W&B）はP1以降。
  - NFR-A54: **GPU監視: `nvidia-smi`または`nvidia-smi dmon`によるGPU利用率・VRAM・温度・電力の定期的記録。Docker環境では`nvidia-ctk`経由でコンテナ内GPUメトリクスを収集。**
  - daemon events、model calls、job resultsをJSONLで記録する。
  - 各ログはjob_idまたはtrace_idを持つ。
  - model callにはprovider、latency、token count、statusを含める。
- **Related Files**: `logs/daemon.jsonl`、`logs/model_calls.jsonl`、`logs/job_results.jsonl`
- **Related Tests**: Phase F logging schema validation test

##### nvidia-smi監視コマンド例

```bash
# リアルタイム監視（1秒間隔）
nvidia-smi --loop=1

# 背景記録（CSV出力）
nvidia-smi --query-gpu=timestamp,name,pci.bus_id,driver_version,pstate,pcie.link.gen.max,pcie.link.width.max,temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.free,power.draw --format=csv -l 1 > logs/gpu_metrics.csv

# Dockerコンテナ内でのGPU確認
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

### 11.7 保守性

#### A-NFR-060: 保守性要件

- **Description**: モジュール分離と文書同期による保守性の確保。
- **Priority**: P0
- **Status**: Policy / Implemented
- **Acceptance Criteria**:
  - NFR-A60: orchestrationの背骨はLangGraphのみ。二重背骨を持たない（ADR-001）。
  - NFR-A61: 関心分離: ingress / daemon / runtime / router / sandbox / squads / audit / promote / hermesをそれぞれ独立モジュール化する。
  - NFR-A62: 文書・README・設計スナップショットのdriftを許容しない。Phase完了時に同期させる（lessons.md由来）。
- **Related Files**: repository structure
- **Related Tests**: scope guard / architecture review

### 11.8 監査性

#### A-NFR-070: 監査性要件

- **Description**: 全状態遷移と操作を追跡可能な監査証跡の確保。
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - NFR-A70: 主要状態遷移とエラーがJSONLで追跡可能。
  - NFR-A71: stateファイルとaudit logの責務を分離する。stateはcache、logはappend-only ground truth。
  - NFR-A72: secret patternを共通モジュール（`scripts/audit.py`）に集中させ、runtime auditとCLI auditが同じパターンを使う。
- **Related Files**: `logs/`、`scripts/audit.py`
- **Related Tests**: T006, Phase F logging tests

### 11.9 ローカルファースト性 / 可搬性

#### A-NFR-080: ローカルファースト性

- **Description**: 外部SaaS不在でも最小運用が可能な可搬性。
- **Origin**: Karpathy
- **Priority**: P0
- **Status**: Policy / Implemented
- **Acceptance Criteria**:
  - NFR-A80: 外部SaaS不在でもMarkdown repositoryとPython scriptsのみで最小運用が可能。
  - NFR-A81: memory / docsに絶対パス/PID/セッションID/API key/相対日時を残さない。
  - NFR-A82: ZIP snapshot配布（`.git`不在）でもprimary integrityを評価可能（Gitはsupplementary evidence）。
- **Related Files**: repository structure
- **Related Tests**: N/A

### 11.10 役割分離

#### A-NFR-090: 役割分離

- **Description**: コード・ファイル権限上での役割分離。
- **Origin**: Karpathy
- **Priority**: P0
- **Status**: Policy / Partially Implemented
- **Acceptance Criteria**:
  - NFR-A90: Brain / Developer / Reviewer / Researcher / Audit / Promote / Hermesはファイル権限上もコード上も分離する。
  - NFR-A91: Brainは`wiki/`直接編集禁止、`scripts/audit.py`実行禁止、git push禁止。
  - NFR-A92: DeveloperはObjective / Instructionの再定義禁止、`AGENTS.md`編集禁止、`scripts/audit.py`編集禁止。
- **Related Files**: `scripts/scope_guard.py`
- **Related Tests**: scope guard tests

### 11.11 失敗時停止性

#### A-NFR-100: 失敗時停止性

- **Description**: 異常検知時に安全側で停止するfail-closed動作。
- **Origin**: Karpathy
- **Priority**: P0
- **Status**: Policy / Implemented
- **Acceptance Criteria**:
  - NFR-A100: audit FAIL / scope violation / max retries / protected path / dependency failureでは先に進まず停止またはBrainに戻す。
  - state file破損時に安全側で停止する。
- **Related Files**: `apps/daemon/wiki_daemon.py`、`apps/runtime/graph.py`
- **Related Tests**: T006, T011

### 11.12 3-tier Sandbox

#### A-NFR-110: 3-tier Sandbox

- **Description**: e2b、local venv、skipの3段階で実行安全性を確保する。
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - e2b unavailable時にlocal venvへfallbackする。
  - sandbox不可時はWARN / fail-closedとして扱う。

| Tier | 実体 | 条件 |
|---|---|---|
| Tier 1 | e2b cloud sandbox | `E2B_API_KEY` 設定時 |
| Tier 2 | local venv (`work/sandbox_venv/`) | 事前検証でvenv利用可 |
| Tier 3 | skip with WARN | Tier 1/2不可時。`success: False` を返し fail-closed |

- **Related Files**: `apps/runtime/sandbox_executor.py`
- **Related Tests**: `test_sandbox_live.py`

---

## 12. セキュリティ・HITL・正本境界要件

### A-INV-001: Status Writer Invariant

- **Description**: 正規のstatus writerは `wiki_daemon` とする。`scripts/approve.py` 等のHITL CLIはHuman CEO / operatorによる明示的承認操作を反映するためにのみ使用される。自律エージェントによるstatus直接更新は禁止する。
- **Origin**: MY_LLMwiki
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - agentがstatusを直接書き換えても、daemonが不当遷移として検知または停止する。
- **Related Files**: `apps/daemon/wiki_daemon.py`、`scripts/approve.py`
- **Related Tests**: T001

### A-HITL-001: 3段階HITL

- **Description**: Gate 1（JOB承認）/ Gate 2（Artifact承認）/ Gate 3（wiki昇格承認）を必須とする。
- **Origin**: NIM-Kinetic
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - 承認メタデータなしでは次段階へ進めない。
  - HITL迂回はP0 bugとして扱う。
  - HITL Gate 1/2/3はCLI（`scripts/approve.py`）経由のみ。Slack経由はMVPではOptional。
- **Related Files**: `scripts/approve.py`、`apps/runtime/graph.py`
- **Related Tests**: T007, T008, T009

### A-BND-001: Canonical Knowledge Boundary

- **Description**: `wiki/` はcompiled knowledgeの正本であり、書き込みはapproved promotion flowに限定する。
- **Origin**: Karpathy-Method
- **Priority**: P0
- **Status**: Implemented
- **Acceptance Criteria**:
  - `promote.py` 以外の正規wiki更新を認めない。
  - auditが直接編集または境界違反を検知する。
- **Related Files**: `scripts/promote.py`、`scripts/audit.py`、`domains/`
- **Related Tests**: T006, T009

### A-BND-002: Hermes Non-Authority

- **Description**: Hermesは補助記憶であり、fact authorityとして読まない。
- **Origin**: Karpathy-Method
- **Priority**: P0
- **Status**: Implemented / Policy
- **Acceptance Criteria**:
  - RAG / Evidence生成時にHermesのみを事実根拠として使わない。
- **Related Files**: `runtime/hermes/`、`scripts/hermes_reflect.py`
- **Related Tests**: T012

---

## 13. 外部統合要件

### 13.1 NVIDIA NIM / Blueprints統合

#### A-NV-001: Hosted NIM-first Routing

- **Description**: LLM RouterはNIMをprimary provider候補として扱う。
- **Priority**: P1
- **Status**: Partially Implemented / Degraded
- **Acceptance Criteria**:
  - 有効なNIM API key設定時にNIMが優先選択される。
  - NIM 401 / 5xx時にOllama fallbackが発動する。
- **Related Files**: `apps/llm_router/router.py`
- **Related Tests**: T004, T005

#### A-NV-002: AI-Q Blueprint as Research Reference

- **Description**: AI-Q BlueprintをResearch Nodeの参照設計として扱う。
- **Priority**: P1
- **Status**: Designed / Deferred
- **Acceptance Criteria**:
  - P1導入時にはshallow/deep routing、citation、checkpointを要件化する。
- **Related Files**: `apps/crew/squads/research_squad/`
- **Related Tests**: Phase G/P1 research tests

#### A-NV-003: RAG Blueprint Deferred

- **Description**: NVIDIA RAG BlueprintはQdrant / embedding / rerank導入時の参照とする。
- **Priority**: P2
- **Status**: Deferred
- **Acceptance Criteria**:
  - MVP内ではQdrant等を必須化しない。
  - 導入時はADRとHuman CEO承認を要する。
- **Related Files**: N/A
- **Related Tests**: Future RAG evaluation

#### A-NV-004: Data Flywheel Blueprint Deferred

- **Description**: Data Flywheel本体はMVP外とし、MVPではログスキーマ準備に限定する。
- **Priority**: P2
- **Status**: Deferred
- **Acceptance Criteria**:
  - MVP文書で自動評価・自動fine-tuningを実装済みと記述しない。
- **Related Files**: `logs/model_calls.jsonl`、`logs/job_results.jsonl`
- **Related Tests**: Phase F logging schema validation test

### 13.2 CLIツール統合

#### A-CLI-001: CLIツール統合基本方針

- **Description**: 各CLIツールは「人間が操作する介助ツール」として導入。自律エージェント化は禁止。役割分担に従い、所定のエージェント補助として使用。
- **Priority**: P0
- **Status**: Policy
- **Acceptance Criteria**:
  - CLIツールは`status`を直接書き換えない。
  - CLIツールはHITL Gateを自動通過しない。
  - CLIツールは`wiki/`に直接書き込まない（promote.py経由のみ）。
  - CLIツールの操作ログは`logs/cli_operations.jsonl`に統一記録。
  - CLIツールは`control-plane/constitutions/global.md`および各CLI専用憲法文書（`CLAUDE.md`/`CODEX.md`/`GEMINI.md`/`KIMI.md`）を遵守する。
- **Related Files**: `control-plane/constitutions/global.md`、`.agent_template/`、`logs/cli_operations.jsonl`
- **Related Tests**: scope guard / manual E2E

#### A-CLI-010: CLI憲法文書体系

- **Description**: 各CLIツールに専用の憲法文書を配置し、プロジェクトの不変則・制約・役割分担を明示する。
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - `CLAUDE.md`: Brain Agent補助としての制約・HITL方針・blackboard書き込み権限を定義。
  - `CODEX.md`: Developer補助としてのコーディング規約・sandbox実行規則・禁止操作を定義。
  - `GEMINI.md`: Research Agent補助としての調査方針・Evidence生成規則を定義。
  - `KIMI.md`: KnowledgeOS補助としての知識管理方針・derive規則を定義。
  - 各CLI憲法文書は`control-plane/constitutions/global.md`の子文書として位置付け、上位原則に反しない。
- **Related Files**: `CLAUDE.md`、`CODEX.md`、`GEMINI.md`、`KIMI.md`、`control-plane/constitutions/global.md`
- **Related Tests**: N/A

#### A-CLI-020: CLI操作ログ統一

- **Description**: CLIツールの全操作を`logs/cli_operations.jsonl`に構造化ログとして記録。
- **Priority**: P0
- **Status**: Policy
- **Acceptance Criteria**:
  - ログ形式: `{"ts":"ISO8601","cli":"claude|codex|copilot|gemini|kimi|openai","operator":"username","action":"read|write|execute","target":"filepath","job_id":"JOB-XXX|N/A","detail":"..."}`
  - write操作は必須。read操作はoption（負荷軽減のため）。
  - `logs/cli_operations.jsonl`はappend-only。
  - ログに`trace_id`（=`job_id`または独立UUID）を付与。
- **Related Files**: `logs/cli_operations.jsonl`
- **Related Tests**: Phase F logging schema validation test

### 13.3 選出GitHubリポジトリ統合

#### A-OSS-001: superpowers統合

- **Description**: `obra/superpowers`をL0 Workspace Scaffoldのmethodology基盤として統合。
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - `npx superpowers`または同等のインストール手順でskills frameworkを導入。
  - `.agent_template/.agent/skills/`にsuperpowers skillsを配置または参照。
  - `AGENTS.md`・`CLAUDE.md`・`RULES.md`を`control-plane/constitutions/`と統合または参照。
  - superpowersの`hooks/`とプロジェクトのHITL Gate conceptを連携（参考）。
- **Related Files**: `.agent_template/`、`control-plane/constitutions/`、`docs/operations/cli_integration_guide.md`
- **Related Tests**: N/A

#### A-OSS-002: antigravity-awesome-skills統合

- **Description**: `sickn33/antigravity-awesome-skills`を追加skillsライブラリとして統合。
- **Priority**: P1
- **Status**: Policy
- **Acceptance Criteria**:
  - `npx antigravity-awesome-skills`またはgit submoduleで`skills/`に追加。
  - 1,435+のSKILL.md playbookから、プロジェクトに関連するskillsを選択インポート。
  - SKILL.md形式はKarpathyの知識管理制度と整合。`docs/`または`.agent_template/`に配置。
- **Related Files**: `.agent_template/.agent/skills/`、`docs/`
- **Related Tests**: N/A

#### A-OSS-003: agentmemory統合（Phase G以降）

- **Description**: `rohitg00/agentmemory`をL1 Knowledge OSの検索・メモリ層強化として統合。
- **Priority**: P1
- **Status**: Deferred
- **Acceptance Criteria**:
  - MCP server経由でLangGraph nodeから呼び出し。
  - BM25 + Vector + Graphの3-stream検索をL1 Knowledge OSに統合。
  - memory lifecycle・confidence scoringはPhase G以降で段階的導入。
- **Related Files**: `runtime/hermes/`、`apps/crew/squads/`、`domains/knowledge_os.py`
- **Related Tests**: Phase G integration tests

#### A-OSS-004: OmniRoute参照（Phase H以降）

- **Description**: `diegosouzapw/OmniRoute`の設計思想を`apps/llm_router/router.py`改善に取り入れる。
- **Priority**: P2
- **Status**: Deferred / Reference only
- **Acceptance Criteria**:
  - OmniRouteのsmart routingアルゴリズム・rate limiting設計・observabilityパターンを設計ドキュメントに反映。
  - 実コードの直接統合は行わない（TypeScript/Node.js製、Pythonプロジェクトとの言語壁）。
  - `routing_config.yaml`の改善にOmniRouteのpolicy DSLを参考にする。
- **Related Files**: `apps/llm_router/router.py`、`apps/llm_router/routing_config.yaml`
- **Related Tests**: Phase H router redesign review

#### A-OSS-005: ccrider統合（Phase H以降）

- **Description**: `neilberkman/ccrider`をHermes補助記憶強化・セッション管理として統合。
- **Priority**: P1
- **Status**: Deferred
- **Acceptance Criteria**:
  - MCP server経由でClaude Code/Codex CLIセッションを検索・browse。
  - LangGraph checkpoint auto-resume（Deferred）の代替/補完として機能。
  - `runtime/hermes/sessions/`にccriderインデックスを統合。
- **Related Files**: `runtime/hermes/`、`apps/daemon/wiki_daemon.py`
- **Related Tests**: Phase H MCP integration tests

#### A-OSS-006: Cabinet統合（Phase I）

- **Description**: `hilash/cabinet`をPhase I外部OSS Pilotとしてsidecar統合。
- **Priority**: P1
- **Status**: Deferred
- **Acceptance Criteria**:
  - `integrations/cabinet/`にsidecar skeletonを構築。
  - read-only / staging-onlyで`domains/`のUI管理を補助。
  - pilot smoke test記録と`docs/weekX_summary.md`評価。
- **Related Files**: `integrations/cabinet/`、`domains/`
- **Related Tests**: Phase I pilot tests

### 13.4 NVIDIA CLIツール統合

#### A-NVIDIA-001: nvidia-ctk統合（Docker GPU前提）

- **Description**: NVIDIA Container ToolkitをDocker運用前提で導入し、コンテナ内からGPUを利用可能にする。
- **Priority**: P0（Docker運用時）/ P2（非Docker時）
- **Status**: Not Implemented
- **Acceptance Criteria**:
  - `nvidia-ctk runtime configure --runtime=docker` でDockerにNVIDIA runtimeを設定。
  - `docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi` でGPUアクセスを検証。
  - Docker Desktop WSL2 backend使用時は、Windows側のWSL2統合設定とnvidia-ctkの両方を確認。
  - `nvidia-ctk`が未インストールの環境では、Docker GPUコンテナを起動しない（graceful degradation）。
  - nvidia-ctkの設定は`docs/operations/docker_setup.md`に手順を記載。
- **Related Files**: `docs/operations/docker_setup.md`
- **Related Tests**: manual verification / Docker smoke test

#### A-NVIDIA-002: nvidia-smi統合（GPU監視）

- **Description**: `nvidia-smi`をGPUリソース監視ツールとして統合。観測性（NFR-A050）の一環として定期実行・記録。
- **Priority**: P1
- **Status**: Operational（ドライバー付属）
- **Acceptance Criteria**:
  - `nvidia-smi`が利用可能な環境では、JOB実行時・負荷試験時にGPUメトリクスを記録。
  - `logs/gpu_metrics.csv`にtimestamp、GPU利用率、VRAM使用量、温度、電力消費を記録（選定的）。
  - Dockerコンテナ内では`nvidia-ctk`経由で`nvidia-smi`を実行。
  - GPU未搭載環境ではnvidia-smi監視をskip（WSL2/Linux互換性維持）。
- **Related Files**: `logs/gpu_metrics.csv`、`scripts/monitor_gpu.py`（Phase F作成）
- **Related Tests**: Phase F benchmark tests

#### A-NVIDIA-003: ngc CLI統合（選定的）

- **Description**: NGC CLIをnvcr.ioレジストリアクセス用に選定的導入。NVIDIAコンテナイメージ・モデルのpullに使用。
- **Priority**: P1
- **Status**: Not Implemented
- **Acceptance Criteria**:
  - `ngc registry image info <image>` でイメージ情報を確認。
  - `docker login nvcr.io` でNGCレジストリに認証（`NGC_API_KEY`）。
  - Triton SDK container等のnvcr.ioイメージをpull可能。
  - Self-hosted NIMはRejectedだが、nvcr.ioからのコンテナ実行はbenchark/検証目的で許容。
  - ngc CLIの認証情報は`.env`に`NGC_API_KEY`として保存（NFR-A040準拠）。
- **Related Files**: `.env.example`、`docs/operations/ngc_setup.md`（Phase G作成）
- **Related Tests**: manual verification

#### A-NVIDIA-004: genai-perf非採用 / AIPerf将来検討

- **Description**: `genai-perf`は公式により"phased out"と宣言されたため本プロジェクトでは非採用とする。後継の**AIPerf**はPhase H以降でSelf-hosted NIM/Triton運用検討時に再評価。
- **Priority**: P2
- **Status**: Rejected / Deferred（AIPerf）
- **Acceptance Criteria**:
  - genai-perfはコードベースに含めない。
  - Phase HでAIPerfを評価し、Self-hosted NIM/Triton benchark要件が発生した場合のみ導入判断。
  - 現状のHosted NIM＋Ollama構成ではbencharkは`model_calls.jsonl`のlatency集計で代替。
- **Related Files**: N/A
- **Related Tests**: N/A

---

## 14. データ・ログ・Data Flywheel準備要件

### 14.1 Data Flywheel-ready Logging Layer

#### A-DATA-001: 構造化JSONLログ

- **Description**: 将来の評価・最適化ループに備え、model callとjob resultを構造化JSONLとして保存する。
- **Origin**: NIM-Kinetic / NVIDIA Data Flywheel Blueprint
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - `logs/model_calls.jsonl` にprovider、model、latency、token count、statusを記録する。
  - `logs/job_results.jsonl` にsuccess/fail/rework/human feedbackを記録する。
  - ログはappend-onlyで扱う。
  - `atomic_append` はtrailing newlineを必ず保証する。
  - 全JSONLはappend-only。
  - 全ログに`trace_id`（=`job_id`）を付与する。
  - 主要イベント: `startup`、`shutdown`、`state_transition`、`validation_error`、`illegal_transition`、`task_execution_error`、`max_retries_exceeded`、`claim_rejected`、`stale_lock_recovered`。
- **Related Files**: `logs/model_calls.jsonl`、`logs/job_results.jsonl`、`logs/daemon.jsonl`
- **Related Tests**: Phase F logging schema validation test

### 14.2 Evidence Retention

#### A-DATA-002: Evidence Retention

- **Description**: JOBごとにEvidence、Artifacts、Decisionを追跡可能にする。
- **Priority**: P0
- **Status**: Implemented / Partial
- **Acceptance Criteria**:
  - JOBからartifact、audit result、approval metadataを追える。
- **Related Files**: `work/jobs/`、`work/blackboard/`、`logs/`
- **Related Tests**: manual E2E / T007-T009

### 14.3 データスキーマ

#### JOB Schema（`docs/JOB_SPEC.md` 準拠）

```yaml
---
job_id: JOB-20250425-001          # required
type: coding | research | review  # required
domain: game | market | personal  # required (Phase B 以降)
squads: [coding_squad, ...]       # optional override
objective: |                       # required
  Clear description of the task
priority: P0 | P1 | P2            # required
status: created | approved_gate_1 | claimed | routed | executing | audit_passed | audit_failed | gate_2_rejected | approved_gate_2 | promotion_pending | approved_gate_3 | promoted | failed | cancelled
parallel: false                   # optional
requires_hitl: true               # optional (default true)
dependencies: []                  # optional
---

# Objective
...

# Scope
...

# Acceptance Criteria
...

# Evidence
...

# Artifacts
...
```

#### JOB frontmatter必須・オプション項目

| 種別 | 項目 |
|---|---|
| **必須** | `job_id`、`type`、`domain`、`status`、`priority`、`objective` |
| **オプション** | `squads`、`parallel`、`assigned_to`、`created_at`、`updated_at`、`tags`、`dependencies`、`requires_hitl` |
| **承認メタデータ** | `approved_by`、`approved_at`（Gate 1）、`approved_gate_2_by`、`approved_gate_3_by`（各gate承認時に自動付与） |

#### Wiki Page Frontmatter（Karpathy 由来）

```yaml
---
source: <raw source path>
promoted_at: YYYY-MM-DD | legacy-unknown
status: compiled | stable | draft
title: <optional>
domain: game | market | personal
job_id: JOB-XXX
---
```

#### daemon_state.json Schema

```json
{
  "last_start": "2026-04-26T12:00:00Z",
  "jobs": {
    "JOB-001": {
      "status": "approved_gate_1",
      "path": "work/jobs/JOB-001.md",
      "created": "2026-04-26T11:50:00Z",
      "last_known_status": "approved_gate_1",
      "retry_count": 0,
      "frozen": false,
      "last_error_code": null
    }
  }
}
```

#### logs/daemon.jsonl（イベント例）

```json
{"ts":"2026-04-26T12:01:00Z","type":"startup","job_id":"daemon","detail":"3 jobs queued"}
{"ts":"2026-04-26T12:01:30Z","type":"state_transition","job_id":"JOB-001","detail":"approved_gate_1 -> claimed"}
{"ts":"2026-04-26T12:02:10Z","type":"validation_error","job_id":"JOB-002","detail":"missing required key: objective"}
{"ts":"2026-04-26T12:02:20Z","type":"illegal_transition","job_id":"JOB-002","detail":"created -> executing (skips gate 1)"}
```

#### logs/model_calls.jsonl（Data Flywheel 互換）

```json
{"ts":"2026-04-26T12:01:35Z","job_id":"JOB-001","provider":"nvidia_nim","model":"qwen/qwen3-coder-480b-a35b-instruct","context":"coding","latency_ms":2300,"prompt_tokens":1200,"completion_tokens":850,"status":"ok","cost_estimate_usd":0.0042}
```

#### Future Data Flywheel Fields（P2以降）

- prompt
- response
- model
- provider
- latency
- token count
- estimated cost
- job outcome
- human feedback
- rework reason
- final approval status

---

## 15. スコープ

### 15.1 MVP In Scope

- CLI ingress
- Slack ingress scaffold / limited operation
- JOB state management
- LangGraph StateGraph
- NIM-first Router + Ollama fallback
- CrewAI squad execution
- Audit Gate
- HITL Gate 1/2/3
- `wiki_daemon`
- `raw → wiki` boundary enforcement
- Hermes reflection
- KnowledgeOS domain isolation
- 3-tier sandbox
- ThreadPoolExecutor-based limited parallelism
- JSONL logging
- Workspace Scaffold（L0）
- Cancel機能
- Blackboardパターン
- **CLIツール統合（役割分担型）— Claude Code, Codex CLI, GitHub Copilot CLI, Gemini CLI, Kimi Code, OpenAI Wrapper**
- **CLI操作ログ統一（`logs/cli_operations.jsonl`）**
- **Docker（WSL2 backend）開発環境標準化 — オプションとして提供**
- **nvidia-ctk — Docker GPU運用時の必須前提**

### 15.2 MVP In Scopeだが限定運用

- NVIDIA NIM: Partial / Degraded。401課題あり。
- AI-Q style Research Squad: simplified / stub-level。
- Slack ingress: CLI primary、Slack secondary。

### 15.3 Out of Scope / Deferred

- Qdrant RAG
- NVIDIA embedding / rerank
- AI-Q Deep Research
- LangGraph checkpoint auto-resume
- Data Flywheel evaluation loop
- PII Guard Models
- Grafana / Prometheus
- Self-hosted NIM
- Cloud GPU / Brev / Helm / Kubernetes
- Kimi provider adapter本格運用
- 第3ドメイン追加（game/market/personal以外）
- **CLIツールの自律的JOB生成・承認・実行（HITLなし）**
- **CLIツールによる直接wiki昇格・promote操作**
- **CLIツール間の相互連携・連鎖実行**
- **Dockerを本番唯一環境として固定（Windows + PowerShellを主環境と維持）**
- **genai-perf本格導入（phased outのため）**

### 15.4 Rejected

- HITLなしのauto-promotion
- HITLなしのauto-merge
- recursive job spawning
- nested LangGraph orchestration
- CrewAI as primary orchestrator
- multi-tenant SaaS in MVP
- FROZEN文書の無承認変更
- 自動cloud delegation / auto-scaling
- self-hosted NIM containers
- ChatDev 2.0採用
- **CLIツールをprimary orchestrator / LLM Router として統合**
- **CLIツールによる自律エージェント化（無人運転）**
- **ngc CLIをNIM API代替として使用（nvcr.ioイメージpullは選定的に許容）**
- dynamic crew / agent generation
- auto-merge to main
- fine-tuning / LoRa training

---

## 16. 受入条件

### 16.1 正本化前確認条件

- [x] 本書が統合正本リポジトリの要件定義であり、新規プロジェクト扱いになっていない。
- [x] FROZEN文書を上書きしないことが明記されている。
- [x] HITL、status writer invariant、LangGraph primary orchestratorが不変則として定義されている。
- [x] NVIDIA BlueprintsがMVP / Deferred / P1 / P2に分類されている。
- [x] Data Flywheelがlogging layerとして表現されている。
- [x] 要件ID、Origin、Status、Acceptance Criteria、Related Files / Testsが付与されている。

### 16.2 Release Gate条件（継続的）

- [ ] `pytest tests/` が全件PASSを維持する。
- [ ] `scripts/scope_guard.py .` がPASSする。
- [ ] Gate 1/2/3を経由する手動E2Eが完走する。
- [ ] NIM key不在時にOllama fallbackが機能する。
- [ ] `promote.py` がGate 3承認なしのwiki書き込みを拒否する。
- [ ] audit FAIL時にpromotionへ進まない。

### 16.3 Phase F受入条件 — Stability Hardening

- [ ] `wiki_daemon` 起動時整合性チェック（A-FR-150）が実装され、testがある。
- [ ] `validation_error` / `illegal_transition` でJOBファイルを書き換えない試験がpytestに組み込まれている。
- [ ] `daemon_state.json` の `last_known_status` 機構が導入され、JOB fileとの矛盾時にlast_known_statusを信頼する。
- [ ] `retry_count` / `frozen` / `last_error_code` の永続化が `daemon_state.json` で行われる。
- [ ] `--all-domains` auditが動作する。
- [ ] `scripts/run_maintenance.py`（rebuild_index → audit → hermes_reflectのchain runner）が実装される。
- [ ] `docs/operations/maintenance_runbook.md` が整備される。
- [ ] PowerShell環境で全pytestが通ること（Windows fixture / encoding対応）。

### 16.4 Phase G受入条件 — Knowledge Layer Hardening

- [ ] `docs/policies/frontmatter_policy.md` 作成
- [ ] `docs/policies/draft_lifecycle_policy.md` 作成
- [ ] `docs/policies/work_semantics.md` 作成
- [ ] `docs/policies/reporting_policy.md` 作成
- [ ] `docs/architecture/external_oss_integration_plan.md` 作成
- [ ] AI-Q Research Node簡易版（intent classifier → shallow / deep research → citations）の動作

### 16.5 Phase H受入条件 — Router & Telemetry

- [ ] NIMの401問題解消（`langchain-nvidia-ai-endpoints`への移行）
- [ ] LangGraph checkpointからの自動resume実装
- [ ] `model_calls.jsonl`からlatency / cost / fallback rateを集計するdashboard草案
- [ ] Kimi provider adapter動作確認

---

## 17. リスクと対策

| リスク | 内容 | 対策 | 優先度 |
|---|---|---|---|
| **制度過剰** | policy docsだけが進み、実運用が遅れる | Phase F受入条件に「動く実装」を必須化、policyはPhase Gで並行整備 | 中 |
| **二重背骨** | LangGraphとCrewAIが両方stateを持ち始める | ADR-001に従いCrewAIをnode内に閉じ込める。crewがstatusを書いたらaudit FAIL | 高 |
| **ロール混線** | Brainがコードを書く、Developerがobjectiveを再定義する | プロンプトとscope_guardで禁止、blackboard上の書き込み権限をaudit | 高 |
| **状態ドリフト** | JOB file / `daemon_state.json` / lockが三者不整合になる | 起動時fail-fast、`last_known_status`をground truth、JSONLをmonotonic証跡に | 高 |
| **正本汚染** | `wiki/`にPROMOTED以外の経路で書き込まれる | `promote.py`が`approved_gate_3_by`をチェック、auditがPROMOTED状態を必須にする | 高 |
| **Hermes正本化** | Hermes memoryが事実sourceとして読まれる | A-BND-002に明記、auditが`runtime/hermes/`参照をEvidenceにした場合FAIL | 中 |
| **NIM障害固着** | NIM 401をignoreしてOllamaだけで運用が定着しNIM検証が形骸化 | Phase H受入条件にNIM 401解消を必須化 | 高 |
| **Slack ingress drift** | 実装はあるが運用されず腐る | Phase Fでメンテナンスモード（NotImplementedError化）か正式運用化を判断 | 低 |
| **並列実行のrace** | `{job_id}_{squad_name}.md`のcleanup race | Phase Fでcleanup戦略を策定。最低限archive保管 | 中 |
| **ZIP配布でのGit evidence欠損** | `.git`不在でauditがfailに見える | NFR-A82のgraceful degradationをauditに組み込み済み | 低 |
| **第3ドメインの誘惑** | game/market/personalを増やしたくなる | Phase H以降、新規ドメイン追加はADR + CEO承認を必須化 | 低 |
| **インシデントレスポンス不在** | セキュリティincident発生時の対応手順が未定義 | `docs/operations/incident_response_playbook.md`をPhase Fで整備 | 中 |
| **ログ容量管理** | JSONLログの無限増大によるディスク圧迫 | ログローテーション戦略（90日保持・アーカイブ）をPhase Fで定義 | 中 |
| **CLIロール混線** | Claude Codeがコードを書く、Codex CLIが設計を変更するなど役割分担が曖昧化 | CLI憲法文書（`CLAUDE.md`/`CODEX.md`等）で制約を明確化。scope_guardで範囲外操作を検知 | 高 |
| **CLI操作の監査不在** | CLIツールの操作がJSONLログに残らず、後追い不能になる | Phase Fで`logs/cli_operations.jsonl`のschema確定と全CLIでの強制ログ出力 | 高 |
| **CLIによる正本汚染** | Kimi CodeやCodex CLIがpromote.py経由以外で`wiki/`を編集 | `scripts/scope_guard.py`にCLI操作の`wiki/`書き込み監視を追加。auditでPROMOTED以外の状態でのwiki変更を検知 | 高 |
| **superpowers導入コスト** | 168k starsの巨大エコシステム導入による複雑性増大 | sidecar-firstで段階的導入。まず`.agent_template/`へのskills配置から開始 | 中 |
| **CLIツール間競合** | 複数CLIが同一ファイルを同時編集してconflict | Blackboardパターンの拡張。CLI操作時のlock機構を検討（Phase F以降） | 中 |
| **OmniRoute誘惑** | TypeScript製OmniRouteを直接統合しようとする | ADRで「設計参照のみ」と明確化。Python製`router.py`の改良方針を堅持 | 低 |
| **agentmemory過剰統合** | Rohit版memory lifecycleがL1 Knowledge OSを複雑化 | Phase GでMCP経由のread-only統合から開始。書き込み統合はADR審議 | 中 |
| **nvidia-ctk未設定によるDocker GPU失敗** | nvidia-ctk未インストール環境でGPUコンテナが動作しない | Phase Fで`docs/operations/docker_setup.md`を整備。未設定環境ではgraceful degradation（CPUフォールバック） | 中 |
| **Windows Docker Desktop WSL2不安定性** | WSL2 backendのGPU統合が不安定・遅い | Windows主環境を維持し、Dockerは選定的オプション。WSL2問題発生時はネイティブWindowsにフォールバック | 中 |
| **nvidia-smiログ肥大化** | `nvidia-smi --loop=1` の継続実行でログが無限増大 | `logs/gpu_metrics.csv`にローテーション適用（90日保持）。負荷試験時のみ詳細記録 | 低 |
| **ngc CLI認証情報漏洩** | `NGC_API_KEY`が`.env`以外に記録される | NFR-A040（secret管理）を厳守。`scripts/audit.py`にNGC key patternを追加 | 高 |
| **genai-perf誘惑** | 古い情報でgenai-perfを導入しようとする | `docs/operations/`にgenai-perf非推奨化を明記。AIPerfのPhase H評価計画を文書化 | 低 |
| **Docker環境のロール混線** | Docker内でCLIツールが誤って`wiki/`や`status`を書き換える | Docker内でも`control-plane/constitutions/global.md`とCLI憲法文書を配置。volume mountで`wiki/`をread-onlyに設定 | 高 |

---

## 18. テスト・検証計画との対応

| Test ID | 検証内容 | 関連要件 |
|---|---|---|
| T001 | duplicate claim防止・状態書き込み権限 | A-FR-020, A-INV-001 |
| T002 | JOB validation | A-FR-010, A-FR-020 |
| T004 | model fallback | A-FR-060, A-NV-001 |
| T005 | NIM routing | A-NV-001 |
| T006 | audit failure block | A-FR-080, A-BND-001 |
| T007 | Gate 1 | A-HITL-001 |
| T008 | Gate 2 | A-HITL-001 |
| T009 | Gate 3 / promotion | A-FR-090, A-HITL-001 |
| T011 | daemon fail-fast / lock | A-FR-020, A-NFR-030 |
| T012 | Hermes non-authority | A-BND-002 |
| T015 | LangGraph orchestration | A-FR-030, A-ARC-002 |
| Phase F logging schema | JSONL schema validation | A-DATA-001, A-NFR-050 |

---

## 19. Phase F以降のロードマップ

### Phase F: Stabilization, Integrity, CLI Foundation, and Docker GPU Environment

目的: Phase Eまでの実装を運用に耐えるレベルに固め、CLIツール統合・Docker GPU環境の基盤を整える。

- `wiki_daemon` 起動時整合性チェック実装 + tests
- `last_known_status` 機構
- `retry_count` / `frozen` の永続化
- `--all-domains` audit
- `scripts/run_maintenance.py`
- `docs/operations/maintenance_runbook.md`
- ログローテーション戦策定義
- PowerShell環境でのpytest対応
- **CLI憲法文書整備**: `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `KIMI.md` の作成と `control-plane/constitutions/global.md` との整合性確認
- **`logs/cli_operations.jsonl` schema確定と実装**
- **`scripts/scope_guard.py` にCLI操作範囲チェック追加**
- **superpowers + antigravity-awesome-skills 導入判断と初期配置**
- **各CLIツールのインストール・認証・動作確認**（Claude Code, Codex CLI, GitHub Copilot CLI, Gemini CLI, Kimi Code, OpenAI Wrapper）
- **Docker（WSL2 backend）環境整備**: `docs/operations/docker_setup.md` 作成
- **nvidia-ctk インストール・設定**: `nvidia-ctk runtime configure --runtime=docker` 検証
- **`docker run --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi` 検証**
- **nvidia-smi 定期監視スクリプト作成**: `scripts/monitor_gpu.py`
- **GPUメトリクスCSV出力**: `logs/gpu_metrics.csv` のschema確定・ローテーション設定

### Phase G: Knowledge, Research Layer, CLI Skills, and NGC Integration

目的: 制度文書とAI-Q researchを揃え、CLIツールのskills統合・ngc CLI導入を強化する。

- `docs/policies/{frontmatter,draft_lifecycle,work_semantics,reporting}_policy.md`
- `docs/architecture/external_oss_integration_plan.md`
- AI-Q Research Node簡易版
- `aiq_research_node.py` + research_squad連携
- citation evidence format
- **antigravity-awesome-skills からプロジェクト固有skillsを選別・インポート**
- **superpowers methodology の本格運用開始（判断済みの場合）**
- **Codex CLI + midudev/autoskills 統合**
- **Gemini CLI Research Squad 連携強化**
- **agentmemory MCP統合の設計・準備**
- **ngc CLI導入**: `docs/operations/ngc_setup.md` 作成、`NGC_API_KEY`設定、nvcr.io認証検証
- **nvcr.ioからのコンテナpull試験**: Triton SDK container等（benchark/検証目的）

### Phase H: NIM Recovery, Router Redesign, CLI Session, and AIPerf Evaluation

目的: NIMを本来のprimaryに戻し、CLIセッション管理・router改善・AIPerf評価を行う。

- NIM 401解消（`langchain-nvidia-ai-endpoints`移行）
- LangGraph checkpoint自動resume
- `model_calls.jsonl`集計dashboard草案
- Kimi provider adapter動作確認
- 新規ドメイン追加のADRプロセス確立
- **ccrider統合（MCP経由）によるCLIセッション検索・resume**
- **OmniRoute設計思想の`router.py`改善への反映**
- **Kimi Code KnowledgeOS連携強化**
- **Claude Code / Codex CLI の本格運用開始と運用手順書整備**
- **AIPerf評価**: genai-perfの後継であるAIPerfをSelf-hosted NIM/Triton benchark観点で評価
- **nvidia-smi GPU benchark統合**: AIPerf実行時のGPUメトリクス同時収集

### Phase I: External OSS Pilot

目的: read-only / staging-onlyのsidecarで外部OSSを1つ接続する。

候補: `hilash/cabinet`（AI-first knowledge base + startup OS）。

- `integrations/cabinet/` skeleton
- pilot smoke test記録
- `docs/weekX_summary.md`相当の評価
- **agno-agi/pal 参照統合（raw→wikiパイプライン改善）**
- **Lanzelot1/claw-brain の`.claude/commands/`パターン参考**

### Phase J: Data Flywheel v1 and CLI Ecosystem Maturity

目的: ログから評価ループを稼働させ、CLIツール統合を成熟させる。

- `eval_samples.jsonl`仕組み
- 簡易dashboard（latency / cost / success rate）
- Data Flywheel Blueprint接続計画
- model quality dashboard
- **全CLIツールの操作品質メトリクス収集**（cli_operations.jsonlからの集計）
- **CLIツール間の役割分担最適化**（使用頻度・成功率の分析）
- **garrytan/gbrain 参照によるナレッジグラフ高度化検討**
- **indexion のcodegraph/KGFパターンのL1 Knowledge OSへの反映検討**

---

## 20. トレーサビリティマトリクス

| Requirement ID | Requirement | Source / Origin | Repository Evidence | Status | Test / Verification |
|---|---|---|---|---|---|
| A-ARC-001 | 5-layer integration | NIM-Kinetic | `apps/`、`domains/`、`work/` | Implemented / Partial | architecture review |
| A-ARC-002 | LangGraph primary orchestrator | ADR-001 | `apps/runtime/graph.py` | Implemented | T015 |
| A-ARC-003 | Control/Data Plane separation | Karpathy / MY_LLMwiki | `work/`、`domains/` | Implemented | T001, T006 |
| A-ARC-004 | Blackboard pattern | MY_LLMwiki | `work/blackboard/`、`apps/runtime/nodes/` | Implemented | T007, T015 |
| A-FR-010 | JOB contract | JOB_SPEC / NIM-Kinetic | `docs/JOB_SPEC.md`、`work/jobs/` | Implemented | T001, T002 |
| A-FR-020 | wiki_daemon | MY_LLMwiki | `apps/daemon/wiki_daemon.py` | Implemented | T001, T011 |
| A-FR-030 | LangGraph flow | NIM-Kinetic | `apps/runtime/graph.py` | Implemented | T007-T009, T015 |
| A-FR-040 | Brain/Developer separation | Karpathy | `plan_executor.py`、`run_executor.py` | Implemented / Partial | T015 |
| A-FR-050 | CrewAI squads | NIM-Kinetic | `apps/crew/` | Implemented / Partial | integration tests |
| A-FR-060 | LLM Router | NIM-Kinetic / NVIDIA NIM | `apps/llm_router/router.py` | Partial / Degraded | T004, T005 |
| A-FR-070 | Domain isolation | Karpathy / NIM-Kinetic | `domains/knowledge_os.py` | Implemented | domain tests |
| A-FR-080 | Audit | Karpathy-Method | `scripts/audit.py` | Implemented | T006 |
| A-FR-090 | Promotion | Karpathy-Method | `scripts/promote.py` | Implemented | T009 |
| A-FR-100 | Hermes reflection | Karpathy-Method | `scripts/hermes_reflect.py` | Implemented / Partial | T012 |
| A-FR-110 | Parallel execution | Phase E | `squad_executor.py` | Implemented | parallel tests |
| A-FR-120 | Cancel | MY_LLMwiki | `scripts/cancel.py` | Implemented | manual E2E |
| A-FR-130 | Workspace scaffold | Karpathy | `.agent_template/`、`control-plane/` | Implemented / Partial | N/A |
| A-FR-140 | YAML validation / transition | MY_LLMwiki | `wiki_daemon.py` | Implemented | T001, T002 |
| A-FR-150 | Startup integrity check | MY_LLMwiki | `wiki_daemon.py` | Implemented / Partial | T001, T011 |
| A-FR-160 | Atomic lock / stale recovery | MY_LLMwiki | `wiki_daemon.py` | Implemented | T001, T011 |
| A-NFR-001 | 実行環境 | NIM-Kinetic | `requirements.txt`、`.env.example` | Operational | manual verification |
| A-NFR-010 | 性能目標 | NIM-Kinetic | `router.py`、`squad_executor.py` | Policy / Partial | Phase F benchmark |
| A-NFR-020 | 可用性 | NIM-Kinetic | `router.py`、`graph.py` | Implemented / Partial | T004, T005 |
| A-NFR-030 | 信頼性 | MY_LLMwiki | `wiki_daemon.py`、`atomic_io.py` | Implemented / Partial | T001, T011 |
| A-NFR-040 | セキュリティ | Karpathy / NIM-Kinetic | `.env.example`、`scope_guard.py`、`audit.py` | Implemented | scope guard tests |
| A-NFR-050 | 観測性 | NIM-Kinetic | `logs/*.jsonl` | Implemented / Partial | Phase F |
| A-NFR-060 | 保守性 | ADR-001 | repository structure | Policy | architecture review |
| A-NFR-070 | 監査性 | Karpathy / MY_LLMwiki | `logs/`、`scripts/audit.py` | Implemented / Partial | T006, Phase F |
| A-NFR-080 | ローカルファースト性 | Karpathy | repository structure | Policy | N/A |
| A-NFR-090 | 役割分離 | Karpathy | `scope_guard.py`、module structure | Policy / Partial | scope guard tests |
| A-NFR-100 | 失敗時停止性 | Karpathy | `wiki_daemon.py`、`graph.py` | Implemented | T006, T011 |
| A-NFR-110 | 3-tier sandbox | NIM-Kinetic | `sandbox_executor.py` | Implemented | sandbox tests |
| A-INV-001 | Status writer invariant | MY_LLMwiki | `wiki_daemon.py`、`approve.py` | Implemented | T001 |
| A-HITL-001 | HITL Gates | NIM-Kinetic | `approve.py`、`graph.py` | Implemented | T007-T009 |
| A-BND-001 | Canonical boundary | Karpathy gist | `promote.py`、`audit.py` | Implemented | T006, T009 |
| A-BND-002 | Hermes non-authority | Karpathy-Method | `runtime/hermes/` | Policy / Implemented | T012 |
| A-NV-001 | NIM routing | NVIDIA NIM | `router.py` | Partial / Degraded | T004, T005 |
| A-NV-002 | AI-Q reference | NVIDIA AI-Q | research squad | Deferred | Phase G |
| A-NV-003 | RAG reference | NVIDIA RAG Blueprint | N/A | Deferred | Future |
| A-NV-004 | Data Flywheel deferred | NVIDIA Data Flywheel | logs | Deferred / Logging only | Phase F |
| A-DATA-001 | Logging layer | Data Flywheel-ready | `logs/*.jsonl` | Implemented / Partial | Phase F |
| A-DATA-002 | Evidence retention | JOB lifecycle | `work/jobs/`、`logs/` | Implemented / Partial | manual E2E |
| A-FR-170 | CLI role allocation | CLI integration strategy | `.agent_template/`、`control-plane/` | Policy / Partial | scope guard |
| A-FR-180 | Claude Code integration | superpowers | `CLAUDE.md`、`work/blackboard/` | Policy / Partial | manual verification |
| A-FR-190 | Codex CLI integration | superpowers / autoskills | `CODEX.md`、`work/artifacts/` | Policy / Partial | sandbox tests |
| A-FR-200 | Copilot CLI integration | superpowers | `.github/copilot/` | Policy | audit tests |
| A-FR-205 | Gemini CLI integration | superpowers | `GEMINI.md`、`work/blackboard/evidence/` | Policy | research tests |
| A-FR-208 | Kimi Code integration | superpowers | `KIMI.md`、`domains/`、`runtime/hermes/` | Policy | domain/hermes tests |
| A-FR-210 | OpenAI Wrapper integration | CLI integration strategy | `apps/llm_router/router.py` | Policy | T004, T005 |
| A-CLI-001 | CLI integration policy | CLI integration strategy | `control-plane/constitutions/` | Policy | scope guard |
| A-CLI-010 | CLI constitutional docs | CLI integration strategy | `CLAUDE.md`、`CODEX.md`、`GEMINI.md`、`KIMI.md` | Policy | N/A |
| A-CLI-020 | CLI operation logging | CLI integration strategy | `logs/cli_operations.jsonl` | Policy | Phase F |
| A-NV-001 | NIM routing | NVIDIA NIM | `router.py` | Partial / Degraded | T004, T005 |
| A-NV-002 | AI-Q reference | NVIDIA AI-Q | research squad | Deferred | Phase G |
| A-NV-003 | RAG reference | NVIDIA RAG Blueprint | N/A | Deferred | Future |
| A-NV-004 | Data Flywheel deferred | NVIDIA Data Flywheel | logs | Deferred / Logging only | Phase F |
| A-OSS-001 | superpowers integration | superpowers | `.agent_template/`、`control-plane/` | Policy | N/A |
| A-OSS-002 | antigravity-awesome-skills | antigravity-awesome-skills | `.agent_template/.agent/skills/` | Policy | N/A |
| A-OSS-003 | agentmemory integration | agentmemory | `runtime/hermes/` | Deferred | Phase G |
| A-OSS-004 | OmniRoute reference | OmniRoute | `apps/llm_router/router.py` | Deferred / Reference | Phase H |
| A-OSS-005 | ccrider integration | ccrider | `runtime/hermes/` | Deferred | Phase H |
| A-OSS-006 | Cabinet integration | Cabinet | `integrations/cabinet/` | Deferred | Phase I |
| A-NVIDIA-001 | nvidia-ctk integration | NVIDIA | `docs/operations/docker_setup.md` | Not Implemented | Phase F |
| A-NVIDIA-002 | nvidia-smi monitoring | NVIDIA | `logs/gpu_metrics.csv` | Operational | Phase F |
| A-NVIDIA-003 | ngc CLI integration | NVIDIA | `.env.example` | Not Implemented | Phase G |
| A-NVIDIA-004 | genai-perf rejected / AIPerf deferred | NVIDIA | N/A | Rejected / Deferred | Phase H |

---

## 21. 更新ルール

1. 要件追加・変更はADRを起票する。
2. Human CEO承認なしにMVP In ScopeへDeferred / Rejected項目を昇格しない。
3. FROZEN文書と矛盾した場合、本書側を修正する。
4. FROZEN文書自体を変更する場合は、解除手続き・ADR・Human CEO承認を必須とする。
5. 本書を `CANONICAL` に昇格するには、Sign-off記録を別ファイルまたは本書末尾に残す。
6. 変更後はトレーサビリティマトリクスとテスト対応表を更新する。
7. リスクテーブル（§17）は各Phase完了時にレビューし、新規リスクの顕在化があれば追加・更新する。
8. 性能目標（§11.2）は各Phaseでベンチマークを実施し、未達項目の改善計画を立てる。

---

## 22. 結論

本書は、統合版v1.0を正本基盤とし、日本語版v1.0の非機能要件詳細・データスキーマ定義・リスク分析・Phaseロードマップ拡張を統合した、より堅牢な要件定義書である。

本プロジェクトの核は、AIエージェントを自由に暴走させることではなく、JOB契約、HITL、daemon-only status writer、LangGraph primary orchestrator、`raw → wiki` 昇格儀式によって、AIの自律性を制度化することにある。

NVIDIA NIM / Blueprints は、本MVPの差別化要素である。ただし、現時点では実装済み基盤・部分実装・将来拡張候補に分類され、MVP内で過大に主張しない。

Phase A〜E は完了しており、43/43 PASSEDの検証ベースを持つ。今後はPhase Fの安定化・整合性強化、Phase Gの制度・research強化、Phase Hのrouter正常化、Phase Iの外部OSS pilot、Phase Jのデータフライホイールへと段階的に拡張する。

Human CEO sign-off後、本書は `CANONICAL` として扱われる。

---

**CANONICAL / FROZEN**

---

## Sign-off Record

- **承認日**: 2026-04-26
- **承認者**: Human CEO (Higurashi)
- **ステータス**: CANONICAL / FROZEN
- **内容**: 
  NIM-Kinetic, Karpathy-Method, wiki-blackboard-daemon の3系統の思想統合を完了し、Phase Gまでの実装成果を反映した本ドキュメントを、プロジェクトの正本（CANONICAL）として正式に認定し、MVP要件を凍結（FROZEN）する。
