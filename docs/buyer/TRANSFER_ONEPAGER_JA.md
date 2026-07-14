# 譲渡説明ワンページ（日本語）

**製品名:** `smbagent` — 日本 SMB 向け **監督付き AI 業務バックエンドのコードフレームワーク一式**  
**取引形態:** コード／知的財産の譲渡（買収側が事業化・運用する）  
**提供モデル:** 1社1台の Mac mini · 重要操作は人が承認

---

## 何を買うのか

買主が受け取るのは **デモの切り出しではなく、`smbagent` のコードフレームワーク全体**です。

具体的には、次を自社で運用・販売できる一式です。

1. 顧客向け5段階ビルド: Qualify → Negotiate → Plan → Code ↔ Validate  
2. 承認・監視・復旧・ループ制御を備えたガバナンス付き運用基盤  
3. 日本向け信頼テンプレート、社長モニター、役割分離ポータル、業界テンプレート、テスト、運用ツール  

これは ChatGPT の代替チャット製品ではありません。  
また「完全自律の AI 社員」を約束するものでもありません。

推奨説明:

> 1社1台の Mac mini 上で動く、監督付きの AI 業務バックエンドです。

---

## 譲渡に含まれる「フレームワーク一式」

| 領域 | パス | 内容 |
|---|---|---|
| **コアフレームワーク** | `smbagent/` | パイプライン、エージェント、ループ制御、ガバナンス、ワークスペース、CLI、業界テンプレ（歯科／不動産／士業）、transport、モニター |
| **ローカル SLM 足場** | `slm/` | 任意のローカル助言層（既定オフ） |
| **ポータル** | `portal/` | 経営者／従業員／運用の入口 |
| **Japan trust** | `japan_trust/` | 方針・告知テンプレート |
| **テスト** | `tests/` | 信頼・ガバナンス・パイプライン回帰 |
| **コンテナ契約** | `containers/` | Apple container 定義 |
| **デモ** | `examples/demo-tokyo-dental/` | 匿名化された完成例 |
| **買主 DD** | `docs/buyer/` | アーキテクチャ、棚卸し、ギャップ、引き継ぎ |
| **導入・運用文書** | ルート `*.md`、`internal_doc/` | デプロイ、セキュリティ、ガバナンス、runbook、ロードマップ |
| **法務メタ** | `LICENSE`、`NOTICE`、`pyproject.toml` | Apache-2.0。著作権譲渡は **別途 SPA** |

導入後、買主は製品本体をそのまま起動できます。

```bash
pip install -e ".[dev]"
smbagent doctor
smbagent new acme-dental
smbagent qualify acme-dental --brief "..."
smbagent run acme-dental
smbagent monitor acme-dental
```

---

## フレームワークではないもの（SPA 除外のみ）

以下は **売主／パートナー固有の袋**であり、`smbagent` フレームワーク本体ではありません。  
`do-not-upload/` にあり、エクスポート対象外です。

| 除外 | 理由 |
|---|---|
| **売主保留のパートナー／顧客向けワークフローパック** | 顧客／パートナー固有 — 本 SPA では除外 |
| 売主の `PRICING.md` / flyer 画像 | 価格・販促は買主が自社設定 |
| 他社ブランドのデモ素材 | 原則として再ライセンスしない |
| 売主の市場ポジション／パイオニア内部メモ | 売主社内資料 |
| IDE 設定、tuning 履歴、ops 実行時 DB | マシン固有。製品 IP ではない |

クリーンな納品:

```bash
./scripts/export_product_tree.sh /tmp/smbagent-transfer
```

このスクリプトは **フレームワーク一式をコピー**し、`do-not-upload/` は **コピーしません**。

**次にフレームワーク詳細を読む:** [`FRAMEWORK_GUIDE_JA.md`](FRAMEWORK_GUIDE_JA.md)  
**契約別紙（資産表）:** [`SPA_SCHEDULE_OF_ASSETS_JA.md`](SPA_SCHEDULE_OF_ASSETS_JA.md)

---

## クロージング後・最初の7日

1. `docs/buyer/PRODUCT_OVERVIEW_JA.md` と `READY_VS_EXPERIMENTAL.md` を読む  
2. Apple Silicon の Mac mini に導入し、`smbagent doctor` と `launch-readiness` を通す  
3. 会社名・サポート窓口・価格表を貴社名義に置き換える  
4. 同梱テンプレートから最初の販売 SKU を **1つ** 選ぶ（例: 歯科）  
5. 機微データを扱う前に Japan trust / 法務チェックを完了する  

詳細: `docs/buyer/HANDOFF_CHECKLIST.md`

---

## 正直な限界（過大広告を避ける）

- **監督付きパイロット**としての販売は妥当。広範な自律 SaaS は未主張  
- `claude` / `codex` / API の実機スモークは **買主環境**で実施が必要  
- ローカル SLM は存在するが **既定オフ**  
- 外部副作用は原則 **HITL（人の承認）**  

---

## 次の読み物

技術 DD 索引: `docs/buyer/README.md`  
English: `docs/buyer/TRANSFER_ONEPAGER_EN.md`
