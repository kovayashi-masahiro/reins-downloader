# REINS 新着・更新物件 自動ダウンロードツール

REINS IP（不動産流通標準情報システム）にログインし、**ワンタッチ検索に保存した
「自動：」で始まる検索条件**を順に実行して、**新着・更新物件の一覧（CSV/Excel）**を
毎日自動で保存します。PDF図面の取得（任意・課金注意）にも対応しています。

このツールは、実際のREINS東日本IP画面（2026年時点）で動作を確認しながら作成しています。

---

## ⚠️ はじめに（重要）

- REINSは宅建業者向けの**会員制システム**です。**ご自身の正規アカウント**でのみ利用してください。
- 自動アクセスはREINSの利用規約で制限される場合があります。規約をご確認のうえ、自己責任でご利用ください。
- ログイン時の「**所属機構の規程及びガイドラインを遵守します**」へのチェックは、ツールが自動で行います（`config.yaml` の `agree_compliance: true`）。これはご自身が当該規程の遵守に同意することを意味します。
- **PDF図面の取得（図面一括取得）は会員プランにより課金される場合があります。** 既定では取得しません（`pdf.download: false`）。課金を理解した上でのみ `true` にしてください。

---

## このツールの動作（確認済みの流れ）

1. REINSにログイン（遵守チェックを自動ON → ログイン）
2. 「売買物件検索」画面を開く
3. ワンタッチ検索の保存条件のうち、**「自動：」で始まるものだけ**を順に実行
   （読込 → 「読込みました」OK → 検索）
4. 検索結果一覧を、**種別タブ・ページ送りを含めて全件読み取り**、CSV / Excel に保存
5. 物件番号で重複を除外。さらに**価格・取引状況の変化（更新）も検知**し、新着・更新だけを保存
6. （任意）`pdf.download: true` の場合のみ、図面を一括取得

> **新着・更新だけに絞るコツ**：各「自動：」保存条件の中で、
> 「**登録年月日＝前日**」「**変更年月日＝前日**」を設定して保存しておくと、その日の新着・更新だけがヒットします。
> 設定しない場合でも、ツールの重複排除により**前回から増えた/変わった物件だけ**が保存されます。

---

## セットアップ手順

### STEP 0. Python を用意
Windows / Mac に **Python 3.10以上**（未導入なら https://www.python.org/ 、Windowsは「Add Python to PATH」にチェック）。

### STEP 1. 必要なものをインストール
- **Mac**: `setup_mac.command` をダブルクリック
- **Windows**: `setup_windows.bat` をダブルクリック

### STEP 2. REINS側で「自動：」検索条件を保存（最重要）
REINSにログイン →「売買物件検索」→ 条件を入力（種別・エリア・登録年月日＝前日・変更年月日＝前日 など）
→ 画面上部「検索条件の保存」に **`自動：○○○`**（先頭が「自動：」）と名前を付けて「保存」。
取得したい条件の数だけ作成してください（例：`自動：渋谷区マンション`）。

> ※ 既に「自動：」付きの条件をお持ちの場合はそのまま使えます。

### STEP 3. ログイン情報を設定
`config.example.yaml` をコピーして **`config.yaml`** にし、`user_id` / `password` を入力。
PDF図面も取得する場合は `pdf.download: true`（**課金注意**）。

### STEP 4. 対象条件の確認（おすすめ）
```
python reins_downloader.py --list-only     # Windows
python3 reins_downloader.py --list-only     # Mac
```
「自動：」付きの保存条件が正しく検出されるか確認できます。

### STEP 5. 実行
```
python reins_downloader.py        # Windows
python3 reins_downloader.py        # Mac
```
- 保存先：`downloads/YYYY-MM-DD/新着更新物件.csv` および `.xlsx`
- PDF（有効時）：同フォルダに保存
- ログ：`logs/`、エラー時：`error_screenshot.png`

初回は `--headed` を付けると画面を見ながら確認できます。

---

## 毎日自動で動かす（朝8:00・ダブルクリックで登録）

### Mac
`install_schedule_mac.command` を**ダブルクリック**するだけで、毎日 朝8:00 に自動実行されます。
（フォルダの場所やPythonのパスは自動で判定されます）
解除は `uninstall_schedule_mac.command` をダブルクリック。

### Windows
`install_schedule_windows.bat` を**右クリック →「管理者として実行」**で、毎日 朝8:00 に登録されます。
解除は `uninstall_schedule_windows.bat` を管理者として実行。

> どちらも **PCが起動している（スリープしていない）必要**があります。
> 時刻を変えたい場合は、Macは `install_schedule_mac.command` 内の `HOUR=8`、
> Windowsは `install_schedule_windows.bat` 内の `/st 08:00` を編集して再登録してください。
> 手動で細かく設定したい場合は `scheduler/` フォルダの旧手順も利用できます。

---

## 出力されるCSV/Excelの列

検索条件 / 物件番号 / 種目 / 取引態様 / 取引状況 / オーナーチェンジ / 価格 / 用途地域 /
土地面積 / 建物面積 / 所在地 / 建物名 / 沿線駅 / 交通 / 商号 / 築年月 / 電話番号 / 取得日時

---

## よくある質問・トラブル

**Q. ログインで止まる**
→ `config.yaml` の `user_id`/`password` を確認。`selectors.login_*` は通常変更不要です。

**Q. 「自動：」の条件が0件と出る**
→ STEP 2 でREINSに「自動：」で始まる検索条件を保存してください。`--list-only` で確認できます。

**Q. 一覧の項目がずれる／取れない**
→ REINSの画面変更が原因の可能性があります。`error_screenshot.png` とログを確認のうえ、`selectors` を調整してください。

**Q. PDFが取得されない**
→ 既定は無効です。`pdf.download: true` に変更してください（課金にご注意）。一括取得時に課金確認画面が出る場合は、初回は `--headed` で挙動をご確認ください。

**Q. 同じ物件が毎日出る／出ない**
→ 重複・更新判定は `state/downloaded.json` で管理しています。最初からやり直す場合はこのファイルを削除してください。

---

## ファイル構成
```
reins-downloader/
├─ reins_downloader.py     … 本体
├─ config.example.yaml     … 設定の見本（コピーして config.yaml を作る）
├─ requirements.txt        … 必要ライブラリ
├─ setup_mac.command / setup_windows.bat  … セットアップ
├─ run.command / run.bat   … 手動実行用
├─ scheduler/              … 毎日自動実行の設定（Win/Mac）
├─ downloads/              … 取得データ（自動生成）
└─ logs/                   … 実行ログ（自動生成）
```
