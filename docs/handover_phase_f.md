# Antigravity Phase F Handover: Infrastructure Hardening & Safety

## 1. Executive Summary
Phase F では、Antigravity システムの「信頼性」と「安全実行」の基盤を確立しました。
AI が生成したコードを実行する際の物理的な隔離（Docker）と、人間が介入して修正を促す論理的なループ（Reject Loop）が完全に統合され、プロダクションレベルの運用に耐えうる「冷徹な観察者」としての骨格が完成しました。

## 2. アーキテクチャの現状

### 2.1 3-Tier サンドボックス実行環境
`apps/runtime/sandbox_executor.py` は以下の 3 段階のフォールバック・セキュリティ階層を備えています：

| Tier | 実行環境 | 用途 | 安全性 |
| :--- | :--- | :--- | :--- |
| **Tier 1** | e2b Cloud | クラウド型サンドボックス（デフォルト） | 最高（完全隔離） |
| **Tier 2** | **Docker Container** | ローカルコンテナ実行（Phase F で実装） | 高（物理隔離） |
| **Tier 3** | Warning/Skip | 実行なし（フォールバック） | - |

- **Docker 実装 (`utils/docker_executor.py`)**:
    - `python:3.12-slim` ベースのカスタムイメージを自動ビルド。
    - ホストの `work/artifacts` のみをマウントし、他へのアクセスを遮断。
    - Linux/WSL2 では UID/GID マッピングを行い、ファイルの所有権問題を解決。

### 2.2 HITL Reject-Loop (拒否・修正ループ)
人間によるレビュー結果を確実にシステムへフィードバックする仕組みを構築しました。

- **`scripts/approve.py --reject --reason "..."`**:
    - ジョブのステータスを `gate_X_rejected` に更新。
    - 拒否理由を JOB ファイル（SSoT）の Markdown ボディに物理的に追記。
- **Graph 復元ロジック**:
    - `load_job` ノードが起動時に JOB ボディを解析し、最新の拒否理由を `review_feedback` として抽出。
    - `plan_executor` がこのフィードバックをプロンプトに注入し、AI が前回の失敗を学習して再試行。

### 2.3 ロギング基盤
- **`utils/logging_config.py`**:
    - `RotatingFileHandler` により `work/system.jsonl` が肥大化するのを防止（10MB x 5世代）。
    - 全ノードで `extra={"job_id": ...}` を付与し、特定のジョブの追跡可能性を確保。

## 3. 運用ガイド

### 3.1 承認・拒否操作
```bash
# Gate 2 (Artifact 生成後) の承認
python scripts/approve.py --gate 2 --job JOB-001

# Gate 2 の拒否（修正指示）
python scripts/approve.py --gate 2 --job JOB-001 --reject --reason "コードにコメントが不足しています。詳細を追記してください。"
```

### 3.2 ログの確認
```bash
# 実行中のジョブのログを抽出
grep "JOB-001" work/system.jsonl
```

## 4. 未解決の課題 / 技術的負債
- **DB 排他制御**: 現在の `wiki_daemon` はシングルプロセス想定。並列実行時のファイルロック競合が Phase G での課題。
- **UI の不在**: すべての HITL 操作が CLI 経由。

---
*Snapshot: 2026-04-26 Phase F 完遂時点*
