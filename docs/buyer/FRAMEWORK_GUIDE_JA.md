# smbagent — フレームワーク詳細紹介（日本語）

本ドキュメントは、**`smbagent` コードフレームワーク全体**の詳細な日本語紹介です。  
何をする製品か、リポジトリ構成、データフロー、運用方法までを一通り説明します。

短い製品紹介（英語）: [`../../INTRODUCTION.md`](../../INTRODUCTION.md)  
短い製品概要（日本語）: [`PRODUCT_OVERVIEW_JA.md`](PRODUCT_OVERVIEW_JA.md)  
英語詳細ガイド: [`FRAMEWORK_GUIDE_EN.md`](FRAMEWORK_GUIDE_EN.md)  
譲渡ワンページ: [`TRANSFER_ONEPAGER_JA.md`](TRANSFER_ONEPAGER_JA.md)

---

## 1. このフレームワークとは

`smbagent` は、日本の中小企業向けに設計された **信頼できる単一テナント型 AI 業務バックエンド** です。

| であるもの | でないもの |
|---|---|
| 1社 · 1台 Mac mini/MacBook · 監督付き基盤 | マルチテナント ChatGPT SaaS |
| リスク境界で人が承認する自動化 | 完全自律の「AI 社員」 |
| Artifact 優先のマルチエージェント構築＋運用 | プロンプトだけのデモ |
| 監査・復旧・監視が可能 | ブラックボックスの常時コンパニオン |

**一言**

> 1社1台の Mac mini 上で動く、監督付きの AI 業務バックエンドです。

譲渡範囲: 買主は **フレームワーク一式** を受け取ります。  
売主保留のパートナー／顧客向けワークフローパックは `do-not-upload/` のみに残る場合があり、それは **フレームワーク欠損ではありません**。

---

## 2. リポジトリ構成（トップレベル）

```text
smbagent/                 # Python パッケージ — コア（製品本体）
slm/                      # 任意のローカル SLM 足場（既定オフ）
portal/                   # 役割分離 HTML（経営者／従業員／運用）
japan_trust/              # 日本 SMB 向け信頼・告知テンプレート
containers/apple/         # Apple container イメージ契約
examples/demo-tokyo-dental/  # 匿名化された完成デモ
tests/                    # 回帰・信頼テスト
docs/buyer/               # 買収・フレームワーク案内（本フォルダ）
internal_doc/             # ロードマップ、思想、運用深掘り
workspaces/               # 実行時顧客データ（納品物ではプレースホルダのみ）
do-not-upload/            # 売主専用（納品しない）— 価格、保留パック、本機ゴミ
```

インストール入口: `pyproject.toml` → CLI コマンド `smbagent`。

---

## 3. 一つのフレームワーク内の二つの姿

### A. 標準顧客ビルドパイプライン

日本語の案件概要／商談を、納品パッケージに変換します。

1. ブランド付きランディング（`code/landing-page/`）
2. 顧客向け AI スキル（`code/agent-skills/`）
3. 連携スタブ（`code/integrations/` — メール、カレンダー、CRM）

### B. ガバナンス付きワークフローバックエンド

継続運用のために次を備えます。

- 会社コンテキスト
- 承認 / HITL
- 社長モニター
- 失敗・ループメモリ
- 運用者向けチューニングと readiness チェック

両者は同じ信頼モデルとワークスペース境界を共有します。

---

## 4. 全体アーキテクチャ

```text
                 会社の Mac mini（単一テナント境界）
                 ┌──────────────────────────────────────┐
                 │  smbagent CLI / 任意の localhost      │
                 │  portal / 社長モニター                │
                 └──────────────────┬───────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
   経営者（読み取り専用）      従業員（狭い入口）         運用者（SSH/CLI）
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    ▼
                    workspaces/<customer_id>/
                    ├── qualification.json, requirements.json, plan.md, …
                    ├── code/
                    ├── runs/round-N/  （checkpoint、verdict など）
                    ├── approvals, monitor, transitions.jsonl
                    └── pipeline_outcome.json（段階的終端時）
```

**隔離ルール:** エージェント同士は **公開 artifact のみ** で連携します。  
非公開の chain-of-thought、ベンダーセッションメモリ、coding の生ログを validation 入力にしてはいけません。

---

## 5. ビルドパイプライン（5段階＋ループ）

```text
Qualify → Negotiate → Plan → (Code ↔ Validate)*N → 任意で Humanize
```

| 段階 | 主なモジュール | 公開成果物 |
|---|---|---|
| Qualify | `agents/qualify.py` | `qualification.json` |
| Negotiate | `agents/negotiation.py` | `requirements.json`, `company_context.json`, 会話録 |
| Plan | `agents/plan.py` | `plan.md`, `tasks.json`（ティア上限チェック） |
| Coding | `agents/coding.py` | `code/` |
| Validation | `agents/validation.py` | `runs/round-N/verdict.json`, feedback |
| Humanize | `humanize_loop.py` ほか | `humanize-round-N/` |

駆動: `orchestrator.py` → Code↔Validate は `pipeline_loop_runner.py`。

Coding と Validation は **別サーフェス**（典型的には Claude coding と Codex validation snapshot）。  
Validation はサニタイズ済みスナップショットを見ます。

---

## 6. ループエンジニアリング（無限エージェントではない理由）

有界反復は第一級のサブシステムです。

| 関心事 | 主要モジュール | 振る舞い |
|---|---|---|
| writer↔critic 共通駆動 | `loop_controller.py` | humanize 等 A↔B ループ |
| 停滞検知 | `loop_stall.py` | 同一 issue／要約の繰り返し、plateau |
| 温度スケジュール | `annealing.py` | creative → convergence → final |
| 探索方針 | `loop_search.py` | continue / replay / branch / stop / escalate |
| チェックポイント | `loop_checkpoint.py` | ラウンドごとの `code/` 保存・復元 |
| 収束メトリクス | `loop_convergence.py` | issue 差分、コード木エントロピー、rubric plateau |
| SLM 助言（任意） | `loop_policy.py`, `slm/` | 信頼度ゲート付き prune/boost（静かな自律化はしない） |
| 段階的終端 | `pipeline_outcome.py` | stop / escalate / humanize_exhausted |
| 状態機械 | `pipeline_state.py` | `derive_state()` + `enforce_pipeline_transition()` |
| 監査リプレイ | `observability/transitions.py` | `smbagent replay --verify` |

思想: **fail-closed** — トークンを燃やし続けるより、停止または人へエスカレーション。

確認コマンド:

```bash
smbagent loop-engineering <customer_id>
smbagent loop-policy <customer_id>
smbagent state <customer_id>
```

---

## 7. 信頼モデル（二車線）

```text
無人レーン（Unattended）              HITL レーン
─────────────────────────            ────────────────────────────────
計画・下書き・分析                     メール／カレンダー／CRM／デプロイ
ワークスペース内の書き込み             ProposedExternalAction
                                     → スキーマ検証
                                     → 安全スキャン
                                     → governance.enforce_action
                                     → 人の承認ログ
```

主要モジュール: `execution_guard.py`, `governance.py`, `approvals.py`, `agent_boundaries.py`, `safety.py`。

Mac mini 商用の既定:

- `SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl`
- `SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false`
- 推奨: `SMBAGENT_SUBPROCESS_ISOLATION=apple-container`

---

## 8. ワークスペースと状態

顧客ごとに `workspaces/<customer_id>/` があります。

| 仕組み | モジュール | 役割 |
|---|---|---|
| Artifact FS API | `workspace.py` | パス、ラウンド、verdict |
| 版付き公開状態 | `workspace_state.py` | OCC + section reducer |
| 形式的パイプライン状態 | `pipeline_state.py` | ディスクから現在状態を導出 |
| 段階的終端 | `pipeline_outcome.py` | 権威ある終端オーバーレイ |

状態は **artifact から導出**されます。オフラインでも「どこで止まったか」が分かります。

---

## 9. 可観測性と復旧

| 対象 | サーフェス |
|---|---|
| 経営者 | `monitor.html`、portal owner、予算姿勢 |
| 従業員 | 狭い portal／スキル入口 |
| 運用者 | CLI、operator dashboard、`maintenance_report.json`、`workflow-check` |

よく使うコマンド:

```bash
smbagent monitor <id>
smbagent maintenance <id>
smbagent workflow-check <id>
smbagent backup <id>
smbagent memory-analytics [--customer <id>]
smbagent tune show --customer <id>
```

学習ログ（生の非公開 CoT は保存しない）: `failure_memory.jsonl`, `loop_memory.jsonl`, usage JSONL, harness manifest。

---

## 10. 業界テンプレートとデモ

フレームワークに同梱:

- `smbagent/templates/dental`（歯科）
- `smbagent/templates/real-estate`（不動産）
- `smbagent/templates/legal`（士業）
- `examples/demo-tokyo-dental/` — 架空の東京歯科クリニック完成例

SPA 注記: 売主保留のパートナー／顧客向けワークフローパックは譲渡アーカイブに含まれません。  
買主はクロージング後、フレームワーク上に自社ワークフローを構築します。

---

## 11. 任意レイヤ（リポジトリには含まれる）

| レイヤ | パス | 既定 |
|---|---|---|
| ローカル SLM | `slm/` + `smbagent/slm/` | オフ — 有効時も助言中心 |
| 音声 ASR/TTS | `smbagent/voice/` + `[voice]` | Apple Silicon ではローカル MLX ASR 推奨 |
| HTTP サーバ | `smbagent/server/` + `[serve]` | Mac mini 既定パスではない（localhost 優先） |
| Game studio | `smbagent/game_studio/` | 実験的 |

---

## 12. 典型的な運用パス

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,voice]"
cp .env.example .env          # 資格情報はローカルのみ — コミット禁止

smbagent doctor
smbagent launch-readiness
smbagent security-readiness

smbagent new acme-dental
smbagent japan-trust-note acme-dental
smbagent qualify acme-dental --brief "東京の歯科クリニック、AI予約とFAQ"
smbagent run acme-dental
smbagent state acme-dental
smbagent monitor acme-dental
```

買主向けクリーンアーカイブ（`do-not-upload/` 除外）:

```bash
./scripts/export_product_tree.sh /tmp/smbagent-transfer
```

---

## 13. 人の役割（UX ではなく製品設計）

| 役割 | 責任 |
|---|---|
| 経営者 | 読み取り専用: 状態、予算、AI が有界であること |
| 従業員 | 狭い入口のみ — 管理権限はない |
| 運用者 | 導入、SSH、承認、チューニング、バックアップ、障害対応 |

この分離は、日本 SMB 向けの「安心」ストーリーの一部です。

---

## 14. フレームワークが主張しないこと

- 広範なマルチテナント SaaS 完成
- 人なしの完全自律運用
- 「セキュリティリスクゼロ」の保証
- 実ローカル LLM なしでの production local-only（現状 `LOCAL_ONLY` は fail-closed）

正直な商用姿勢: **監督付きパイロット／マネージド appliance**。  
ガバナンスと復旧に強い。

---

## 15. 次に読む文書

| 目的 | 文書 |
|---|---|
| 英語詳細ガイド | [`FRAMEWORK_GUIDE_EN.md`](FRAMEWORK_GUIDE_EN.md) |
| アーキテクチャ | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| モジュール棚卸し | [`MODULE_INVENTORY.md`](MODULE_INVENTORY.md) |
| Ready vs experimental | [`READY_VS_EXPERIMENTAL.md`](READY_VS_EXPERIMENTAL.md) |
| 譲渡範囲 | [`TRANSFER_ONEPAGER_JA.md`](TRANSFER_ONEPAGER_JA.md) |
| セキュリティ | [`../../SECURITY.md`](../../SECURITY.md) |
| ガバナンス | [`../../GOVERNANCE.md`](../../GOVERNANCE.md) |
| Mac mini セットアップ | [`../../MAC_SETUP.md`](../../MAC_SETUP.md) |
| Runbook | [`../../RUNBOOK.md`](../../RUNBOOK.md) |
| 思想 | [`../../internal_doc/PHILOSOPHY.md`](../../internal_doc/PHILOSOPHY.md) |
| 顧客向け説明 | [`../../CUSTOMER_EXPLANATION_JA.md`](../../CUSTOMER_EXPLANATION_JA.md) |
