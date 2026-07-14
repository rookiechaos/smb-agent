# SPA 資産表（日本語・ワンページ）

**契約別紙。** 日本企業が `smbagent` を事業化するための IP 譲渡／事業譲渡契約に添付する。

| 項目 | 内容 |
|---|---|
| 製品名 | `smbagent` |
| 譲渡形態 | コード＋文書フレームワークの技术转让（技術譲渡） |
| 納品媒体 | `scripts/package_transfer_release.sh` によるチェックサム付きアーカイブ |
| ライセンス表記 | 同梱 Apache-2.0。**商業上の著作権譲渡は本 SPA が規律** |
| 著作者表記の基準 | `NOTICE` / `LICENSE` — “Copyright 2026 the smbagent authors” |

---

## A. 含まれる資産（買主が受領）

| # | 資産 | パス／内容 |
|---|---|---|
| A1 | コアフレームワーク | `smbagent/` |
| A2 | ローカル SLM 足場（既定オフ） | `slm/` |
| A3 | 役割分離ポータル | `portal/` |
| A4 | Japan trust テンプレート | `japan_trust/` |
| A5 | Apple container 契約 | `containers/` |
| A6 | 自動テスト | `tests/` |
| A7 | デモワークスペース例 | `examples/demo-tokyo-dental/` |
| A8 | 買主 DD・フレームワーク案内 | `docs/buyer/`（本資産表を含む） |
| A9 | 導入・保安・運用文書 | 納品ツリー上のルート `*.md` および `internal_doc/`（売主除外分を除く） |
| A10 | ビルド／CI／スクリプト | `pyproject.toml`、`.github/`、`scripts/`、`.env.example`、`.gitignore` |
| A11 | 法務メタ | `LICENSE`、`NOTICE` |
| A12 | 納品 provenance | 梱包時の `PROVENANCE.txt`、`TRANSFER_MANIFEST.txt`、`*.tar.gz` と `*.sha256` |

**「フレームワーク一式」の意味:** 除外パックなしでも、導入・`doctor`・顧客ワークスペース作成・5段階パイプライン・モニター／ガバナンス運用が可能。

---

## B. 除外資産（売主が保持・アーカイブに含めない）

| # | 資産 | パス | 理由 |
|---|---|---|---|
| B1 | パイオニア／パートナー WF パック | 売主の `do-not-upload/` のみ（アーカイブ外） | 顧客／パートナー固有。SPA 対象外 |
| B2 | 売主料金表 | `do-not-upload/PRICING.md` | 価格は買主が設定 |
| B3 | 売主販促画像 | `do-not-upload/flyer.png` | 売主ブランド |
| B4 | 他社ブランドデモ素材 | `do-not-upload/examples/partner-demo/` | 原則再ライセンスしない |
| B5 | 売主内部メモ | `do-not-upload/internal_doc/*` | 売主社内 |
| B6 | 本機 IDE／ops／tuning 状態 | `do-not-upload/local-ide/` 等 | マシン固有。製品 IP ではない |
| B7 | 秘密情報 | `.env`、API キー、トークン | 譲渡しない |

納品ツリー上のルート `PRICING.md` は **差し替え必須のプレースホルダ**であり、売主料金表のライセンス供与ではない。

---

## C. 開示事項（本表と一体）

1. **Provenance／著作者。** 梱包時点で git コミット履歴がない場合、法務は (i) 本資産表、(ii) `NOTICE`/`LICENSE`、(iii) アーカイブ `sha256` と `PROVENANCE.txt` の content-tree hash を根拠とする。後から curated git tag を付けることは運用上の整理であり、資産特定の成立条件ではない。  
2. **過去の市場表現。** 初期草稿に第三者製品名を deliverable 形状のたとえで用いた箇所があった。譲渡に向けて現行 prompts／コードコメントは scrub 済み。残存表現があっても記述上の残滓にすぎず、**商標権・ソフト許諾・提携関係を付与または暗示しない**。  
3. **価格。** 売主料金表は除外。顧客提案前にルート `PRICING.md` を買主名義で必ず差し替え。  
4. **含まれないもの。** 実顧客の学習データ、本番 workspaces、クラウド契約、再販契約は、書面補正がない限り本表の外。  
5. **規制保証なし。** Japan trust テンプレートは運用者の確認を助けるものであり、全業種・全顧客の法令適合を証明しない。

---

## D. 技術的受領確認

次がすべて真であるとき、買主は受領を確認する。

- [ ] `*.tar.gz` と対応する `*.sha256` を受領した  
- [ ] `shasum -a 256 -c …sha256` が成功する  
- [ ] ツリーに A1–A12 があり、`do-not-upload/` が無い  
- [ ] `docs/buyer/SPA_SCHEDULE_OF_ASSETS_EN.md` と `_JA.md` がある  
- [ ] ルート `PRICING.md` が buyer-must-replace である  

梱包コマンド:

```bash
./scripts/package_transfer_release.sh /tmp
```

---

## E. 署名欄

| 役割 | 氏名 | 日付 | 署名 |
|---|---|---|---|
| 売主 | | | |
| 買主 | | | |

English: [`SPA_SCHEDULE_OF_ASSETS_EN.md`](SPA_SCHEDULE_OF_ASSETS_EN.md)
