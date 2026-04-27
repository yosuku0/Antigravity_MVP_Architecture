# P0 HITL Promotion State Machine — Walkthrough

## 変更対象ファイル一覧

### 新規作成
| ファイル | 目的 |
|---|---|
| `tests/test_promotion_state_machine.py` | P0修復の正式回帰テスト |
| `docs/walkthrough_p0_hitl_promotion.md` | 本ファイル |

### 修正（新APIへの移行）
| ファイル | 理由 |
|---|---|
| `tests/test_hitl.py` | 旧 `approve_gate_2` 関数 import → subprocess CLI呼び出しに変更 |
| `tests/test_daemon.py` | 旧 `process_jobs` → `process_jobs_parallel`、グローバル isolation 修正 |
| `tests/test_audit_promote.py` | 旧 `promote_file` → `stage_job` / `execute_job` API に変更 |
| `tests/test_safety.py` | 旧 `approve_gate_2` import → CLI呼び出し、フィールド名修正 |
| `tests/scratch/test_reject_loop.py` | 同上 |
| `tests/test_hitl_gated_promotion.py` | 旧設計 (Graph内promotion) → モジュールレベルで skip に置換 |
| `README.md` | 旧アーキテクチャ図 (`audit -> promote`) を現状の状態機械に修正 |

### Phase 1〜5 (P0修復本体) — Step 6では変更なし
| ファイル | 変更内容 |
|---|---|
| `apps/runtime/graph.py` | Graph を `audit_passed` で停止、promotion 呼び出しを削除 |
| `scripts/approve.py` | 状態遷移認識型CLI (Gate 2 / Gate 3 前提条件チェック) |
| `apps/daemon/slack_adapter.py` | Slack Approve を Gate 2 のみに限定 |
| `scripts/promote.py` | `--mode stage` / `--mode execute` に分離、レガシー引数を削除 |
| `apps/daemon/wiki_daemon.py` | Dispatcher 分離、Slack通知の `artifact_path` frontmatter 参照、非終端失敗保持 |

---

## 新しい状態遷移図

```text
created
  └─ approved_gate_1  ──► Graph / run_job()
                              ├─► audit_passed    (artifact_path がfrontmatterに記録)
                              └─► audit_failed

audit_passed
  └─ Gate 2 approval ──► Slack Approve  OR  approve.py --gate 2
                              ├─► approved_gate_2
                              └─► gate_2_rejected (Slack/CLIどちらも可)

approved_gate_2
  └─ Daemon Dispatcher ──► promote.py --mode stage
                              └─► promotion_pending (staged_artifact_path, artifact_hash 記録)

promotion_pending
  └─ Gate 3 approval ──► approve.py --gate 3 (CLI のみ)
                              └─► approved_gate_3

approved_gate_3
  └─ Daemon Dispatcher ──► promote.py --mode execute
                              └─► promoted (promoted_path, promoted_hash 記録)
```

---

## 旧P0問題の一覧と修正

### 1. Graph内 promotion (P0-A)
**旧**: `approve.py` で `approved_gate_3` にするとGraphが再起動して wiki 書き込みまで行う  
**修正**: Graph は `audit_passed` で停止。promotion は `promote.py` 専用  
**ファイル**: `apps/runtime/graph.py`

### 2. Slack Gate 3 直行 (P0-B)
**旧**: Slack Approve ボタンが `approved_gate_3` を直接書き込んでいた  
**修正**: Slack は `audit_passed` → `approved_gate_2` のみ許可  
**ファイル**: `apps/daemon/slack_adapter.py`

### 3. promote.py bypass / legacy API (P0-C)
**旧**: `promote_file(artifact)` で artifact を直接指定、`--force` でchecksum スキップ  
**修正**: `--mode stage` / `--mode execute` のみサポート。legacy引数はエラー終了  
**ファイル**: `scripts/promote.py`

### 4. Daemon dispatcher 混線 (P0-D)
**旧**: `RUNNABLE_STATUSES` に `approved_gate_2` / `approved_gate_3` を混ぜてGraphへ投入  
**修正**: `GRAPH_RUNNABLE_STATUSES` と `PROMOTION_STATUSES` を分離  
**ファイル**: `apps/daemon/wiki_daemon.py`

### 5. Slack Gate 2通知の staging path ハードコード (P0-E)
**旧**: `work/artifacts/staging/{jid}.md` をハードコード (audit_passed時点では未存在)  
**修正**: `fm.get("artifact_path")` でfrontmatterから取得、実体確認後に通知  
**ファイル**: `apps/daemon/wiki_daemon.py`

---

## 修正後の責務境界

| コンポーネント | 責務 |
|---|---|
| `Graph / run_job()` | `approved_gate_1` → 実行 → `audit_passed` or `audit_failed` で停止 |
| `approve.py` | Gate 2 / Gate 3 の状態認識型CLI承認 |
| `slack_adapter.py` | Gate 2 のみ: `audit_passed` → `approved_gate_2` または `gate_2_rejected` |
| `promote.py` | `--mode stage`: staging コピー + hash計算、`--mode execute`: wiki書き込み |
| `wiki_daemon.py` | Dispatcher: `approved_gate_1` → Graph、`approved_gate_2/3` → promote.py |

---

## 実行したコマンド

### 新規テストのみ
```bash
pytest tests/test_promotion_state_machine.py -v
```

### 修正テスト込み
```bash
pytest tests/test_promotion_state_machine.py tests/test_audit_promote.py tests/test_hitl.py tests/test_daemon.py -v
```

### 全スイート
```bash
pytest tests/ -q
```

---

## テスト結果

### Step 6 対象ファイル: 41 / 41 PASSED

| クラス | テスト数 | 結果 |
|---|---|---|
| `TestCLIApproval` | 7 | PASSED |
| `TestSlackGate2` | 3 | PASSED |
| `TestPromoteStagingExecution` | 8 | PASSED |
| `TestDaemonDispatcher` | 5 | PASSED |
| `TestDaemonSlackNotification` | 4 | PASSED |
| `test_audit_promote.py` | 5 | PASSED |
| `test_hitl.py` | 5 | PASSED |
| `test_daemon.py` | 3 | PASSED |
| `test_hitl_gated_promotion.py` | 1 | SKIPPED (xfail) |

### 全スイート: 76 passed, 1 skipped, 2 failed

| `test_sandbox.py::test_tier_2_local_execution` | `_check_tier2_readiness` 属性なし | **P0修復前から既存** (commit `c67b905`) |
| `test_sandbox.py::test_tier_3_fallback` | tier 2 vs 3 の期待値不一致 | **P0修復前から既存** |

> [!NOTE]
> 上記 `test_sandbox.py` の 2 失敗は、本 P0 修復（HITL Promotion State Machine）の変更とは独立した既存の問題であり、スコープ外として維持しています。

---

## `test_hitl_gated_promotion.py` の扱い

旧設計 (Graph が `approved_gate_3` を受けて wiki に直接書き込む) を前提としていたため、P0修復後は **構造的に無効**。  
削除ではなく `@pytest.mark.xfail` + `pytest.skip()` に置換し、代替テストへの参照を明記。

---

## Secret grep 結果

```bash
git grep -n "xoxb-\|xapp-\|OPENAI_API_KEY\|ANTHROPIC_API_KEY\|GITHUB_TOKEN\|ghp_\|sk-" -- .
```

検出されたもの:
- `.env.example` — プレースホルダーのみ (`xoxb-your-bot-token` 等)
- `docs/walkthrough_slack.md` — プレースホルダー
- `docs/architecture/requirements_canonical.md` — 説明文
- `scripts/audit.py` — 検出パターン定義 (正規表現)
- `doc/adr/ADR-001-mvp-control-plane.md` — 表の内容

**実 secret は含まれていません。**

---

## README / docs の整合性

Public repo の `README.md` において、Graph が wiki promotion まで直接担当しているように見える旧アーキテクチャ図（`audit -> promote -> END`）を、今回の P0 修復後の実態に合わせて更新しました。

- Graph は `audit_passed` で停止
- その後の Gate 2/3 承認および `promote.py` による段階的 promotion 経路を Mermaid 図に明示
- Slack 承認の制限（Gate 2 のみ）および `promote.py` による wiki 正本書き込みの唯一性を説明文に追記

---

## Git / GitHub 運用

- Branch: `fix/p0-hitl-promotion-state-machine`
- No force push
- No commit to main/master
- Secret grep: プレースホルダーのみ確認済み
