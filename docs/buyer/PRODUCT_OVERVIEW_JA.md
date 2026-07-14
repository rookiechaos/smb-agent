# smbagent 製品概要（譲渡・買収向け）

## 一言で言うと

`smbagent` は、日本の中小企業向けに設計された **監督付き AI 業務バックエンドのコードフレームワーク** です。

譲渡で買主が受け取るのは **フレームワーク一式**（コア・テンプレート・ポータル・テスト・運用文書）です。  
ChatGPT のチャット代替ではなく、**会社専用の運用基盤を自社で展開・販売できる一式**です。

- 会社ごとに専用の Mac mini / MacBook を置く
- AI が定型業務の下書き・分析・ワークフロー準備を行う
- 重要な外部実行は **人が承認**
- 社長向けの読み取り専用モニターで進捗が見える

## 売れる形（推奨）

| 項目 | 内容 |
|---|---|
| 提供形態 | 1社1台の managed appliance（マルチテナント SaaS ではない） |
| 初期適合 | パイロット / 監督付き導入 |
| 強み | ガバナンス、監査、復旧、会社境界、ループ制御 |
| 非主張 | 完全自律の AI 社員、無人の本番実行 |

推奨セールストーク:

> 1社1台の Mac mini 上で動く、監督付きの AI 業務バックエンドです。  
> 重要操作は人が承認し、社長は進捗をモニターで確認できます。

## 技術の核

1. **5段階ビルドパイプライン**  
   Qualify → Negotiate → Plan → Code ↔ Validate
2. **公開 artifact のみでエージェント連携**  
   非公開の chain-of-thought / 私有メモリは共有しない
3. **有界ループ**  
   無限リトライではなく、停止・人確認・自然化上限などの明確な終端
4. **HITL（人の承認）**  
   外部副作用は execution guard を通過後に承認
5. **日本向け信頼設計**  
   ローカル優先、LAN モニター、`japan_trust/` テンプレート

## 顧客に最初に見せるもの

1. [`CUSTOMER_EXPLANATION_JA.md`](../../CUSTOMER_EXPLANATION_JA.md)
2. [`SALES_ONEPAGER_JA.md`](../../SALES_ONEPAGER_JA.md)
3. Owner monitor（`smbagent monitor <customer_id>`）
4. 歯科など業界テンプレートのデモ（`examples/demo-tokyo-dental/`）

## 買手企業が引き継いだ後にやること

1. ブランド・価格・サポート窓口を自社に置き換える
2. 実機 Mac mini で `doctor` / `launch-readiness` / smoke を完了する
3. 同梱の業界テンプレートから最初のパイロット SKU を1つに絞る
4. （参考）売主保留の顧客／パートナー向けワークフローパックは本 SPA 対象外。必要なら自社ワークフローを新規に作る

詳細は [HANDOFF_CHECKLIST.md](HANDOFF_CHECKLIST.md) と
[TRANSFER_ONEPAGER_JA.md](TRANSFER_ONEPAGER_JA.md) を参照してください。
