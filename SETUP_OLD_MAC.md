# 古い Mac での セットアップ手順

このドキュメントは、別の Mac（自動実行専用機）での初期セットアップ方法です。

---

## 📋 セットアップ手順

### **ステップ1: クローン**

```bash
cd ~/Documents/ai
git clone https://github.com/kovayashi-masahiro/reins-downloader.git
cd reins-downloader
```

### **ステップ2: config.yaml を作成（認証情報を入力）**

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

ファイルが開いたら、以下を編集：
```yaml
login:
  user_id: "YOUR_USER_ID"      # ← ここに REINS の ユーザーID を入力
  password: "YOUR_PASSWORD"    # ← ここに パスワード を入力
```

保存方法：
- **Ctrl + X** を押す
- **Y** を押す
- **Enter** を押す

### **ステップ3: 依存パッケージをインストール**

```bash
chmod +x setup_mac.command
./setup_mac.command
```

### **ステップ4: 手動実行でテスト**

```bash
python3 reins_downloader.py --headed
```

ブラウザが開いて、REINS に自動ログインし、検索が実行されるはず。

完了すると：
```
✅ 完了しました
出力ファイル: downloads/ フォルダを確認してください
```

### **ステップ5: 自動実行スケジュール設定**

```bash
chmod +x install_schedule_mac.command
./install_schedule_mac.command
```

完了すると：
```
✅ 登録しました。毎日 8:00 に自動実行されます。
```

---

## 🔧 Mac をスリープさせないように設定

毎朝8:00に確実に実行するため、Mac がスリープしないようにします：

### **方法A: システム設定から**

1. **「システム設定」を開く**
2. **「バッテリーとスリープ」 → 「スリープを解除しない」**
3. **ディスプレイも「スリープを解除しない」**

### **方法B: ターミナルから**

```bash
# スリープを完全に無効化
sudo pmset sleep 0
sudo pmset displaysleep 0
```

解除したい時：
```bash
sudo pmset sleep 10
sudo pmset displaysleep 10
```

---

## 📊 ログを確認

毎日の実行状況を確認：

```bash
# 最新のログを見る
tail -50 ~/Documents/ai/reins-downloader/logs/launchd.out.log
tail -50 ~/Documents/ai/reins-downloader/logs/launchd.err.log
```

---

## 📁 出力ファイルの場所

毎日 8:00 に、以下の場所に新着・更新物件が保存されます：

```
~/Documents/ai/reins-downloader/downloads/YYYY-MM-DD/
  ├── 新着更新物件.csv
  └── 新着更新物件.xlsx
```

---

## 🔄 コードを更新したい場合

最新版を取得：

```bash
cd ~/Documents/ai/reins-downloader
git pull origin main
```

---

## ⚠️ 自動実行を解除したい場合

```bash
./uninstall_schedule_mac.command
```

---

## ❓ トラブルシューティング

### スケジュール登録に失敗した場合

```bash
# 古いスケジュール登録を削除
launchctl unload ~/Library/LaunchAgents/com.reins.daily.plist
rm ~/Library/LaunchAgents/com.reins.daily.plist

# 再度インストール
./install_schedule_mac.command
```

### Python が見つからない場合

```bash
python3 --version
# Python 3.10 以上が表示されることを確認
```

表示されない場合は、Python をインストール：
https://www.python.org/downloads/

---

**質問があれば、メインの README.md を参照するか、サポートを求めてください。**
