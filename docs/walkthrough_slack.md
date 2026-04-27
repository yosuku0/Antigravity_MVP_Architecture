# Antigravity Slack HITL Walkthrough

> **Boundary note:**
> Slack is limited to Gate 2 notification, approval, and rejection.
> Slack cannot perform Gate 3 and cannot write canonical wiki content.
> LangGraph stops after audit and has no `promote` node.
> Canonical wiki writes occur only through `scripts/promote.py --mode execute` after Gate 3 CLI approval.


## 1. Setup & Environment
Slack 連携を有効にするには、以下の環境変数を `.env` に設定する必要があります。

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C...
SLACK_ADMIN_USER_IDS=U...,U... # カンマ区切り
```

## 2. 起動確認
`wiki_daemon.py` を起動すると、ログに以下のメッセージが表示されます：
```text
2026-04-26 17:15:00 [INFO] daemon: Slack Adapter started (Socket Mode)
2026-04-26 17:15:01 [INFO] slack_bolt.adapter.socket_mode.socket_mode_handler: Socket Mode handler is now online!
```

## 3. HITL サイクル（実機検証済み）
以下の手順で Slack 上での Gate 2 承認・却下フローが完結することを確認しました。

### 3.1 通知 (Audit Pending)
- ジョブが `audit_passed` になると、Slack チャンネルに **[Approve] [Reject]** ボタン付きの Block Kit メッセージが投稿されます。
- 同時に、JOB ファイルに `slack_ts` が書き込まれ、二重通知が防止されます。

### 3.2 承認操作 (Approve)
- 管理者が **[Approve ✅]** をクリック。
- **内部処理**: `slack_adapter.py` が `is_authorized` をチェック。
- **結果**: 
    - 物理 JOB ファイルのステータスが `approved_gate_2` に更新。
    - Slack のメッセージが「✅ *Approved by @user*」に書き換わる。
    - **Slack approval is Gate 2 only.** Gate 3 remains CLI-only via `scripts/approve.py --gate 3`.
    - `wiki_daemon` が次回のループでジョブを検知し、`scripts/promote.py --mode stage` を実行します。

### 3.3 拒否操作 (Reject)
- 管理者が **[Reject ❌]** をクリック。
- **内部処理**: モーダルが表示され、理由を入力。
- **結果**:
    - 物理 JOB ファイルに拒否理由が追記され、ステータスが `gate_2_rejected` に更新。
    - Slack メッセージが「❌ *Rejected by @user*」に書き換わる。
    - メタデータ項目: `rejected_gate: 2`, `rejected_by`, `rejected_at`, `reject_reason`

## 4. セキュリティ・ガード
- **ホワイトリスト**: `SLACK_ADMIN_USER_IDS` に含まれないユーザーがボタンを押した場合、本人にのみ見える（ephemeral）警告メッセージが表示され、処理は拒否されます。
- **Socket Mode**: ファイアウォール設定なしで、アウトバウンド接続のみで安全に動作します。
