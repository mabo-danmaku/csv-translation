# CSV翻訳ツール

このツールは、CSVファイル内の特定の列を [DeepL API](https://www.deepl.com/pro-api) を使用して翻訳する Python スクリプトです。  
個人利用を目的としてAIによって生成され、一部手動で修正・調整を行いました。  
動作の保証はできませんので、ご自身の環境で十分にテストした上でご利用ください。

## 📌 このツールが向いている人
- CSV形式のデータを多言語対応させたい人
- DeepLの高精度な翻訳をスクリプトで活用したい人

---

## 🔹 主な機能
- ✅ DeepL APIを利用した高精度な翻訳
- ✅ CSVファイルの特定の列を翻訳し、元の列に上書き
- ✅ 列の指定方法は「列名」または「列インデックス」から選択可能
- ✅ 翻訳の進捗状況をリアルタイムで表示
- ✅ エラー処理や空セルの適切な管理

---

## 💻 動作環境
- **Python 3.6以上**
- 必要なPythonパッケージは `requirements.txt` に記載

---

## 🛠 インストール方法

### 1️⃣ リポジトリのクローンまたはダウンロード
```bash
git clone https://github.com/mabo-danmaku/csv-translation.git
cd csv-translation
```

### 2️⃣ 必要なパッケージのインストール
```bash
pip install -r requirements.txt
```

### 3️⃣ DeepL APIキーの取得と設定
1. [DeepL API](https://www.deepl.com/pro-api) に登録（無料・有料プランあり）
2. APIキーを取得
3. プロジェクトディレクトリに `.env` ファイルを作成し以下のようにAPIキーを設定
```
DEEPL_AUTH_KEY=your_api_key_here
```

---

## 🚀 使い方

### 1️⃣ スクリプトの実行
```bash
python csv-translation.py
```

### 2️⃣ CSVファイルのパスを入力
```
翻訳したいCSVファイルのパスを入力してください: D:\path\to\csv\example.csv
```

### 3️⃣ CSVのヘッダー有無を指定
```
CSVファイルにヘッダー行がありますか？ (y/n): y
```

### 4️⃣ 翻訳する列を選択
- 列名で指定 → `1`
- インデックスで指定 → `2`
```
列の指定方法を選択してください（1: 列名, 2: インデックス）: 1
```

### 5️⃣ 列名またはインデックスを入力

#### 🔹 列名で指定する場合（ヘッダー行があるCSV）
```
翻訳する列名を入力してください: Dialogue
```

#### 🔹 インデックスで指定する場合（0始まり）
```
翻訳する列のインデックスを入力してください（0始まり）: 1
```
（例：CSVの2番目の列を翻訳したい場合、インデックスは `1` ）

### 6️⃣ 翻訳結果の保存
翻訳が完了すると、結果は `output.csv` として保存されます。

---

## ⚠ 注意点
- 空のセルは翻訳されず、そのまま保持されます。
- 翻訳処理中にエラーが発生した場合、元のテキストが保持されます。
- **DeepL APIの無料プランでは、1か月あたり50万文字まで翻訳可能**です（2025年現在）。
- 翻訳後は、内容を確認することを推奨します。

---

## ❓ トラブルシューティング

| 問題 | 解決方法 | 
|------|---------|
| **DeepL APIキーが設定されていません** | `.env` ファイルが正しく作成され、有効なAPIキーが含まれているか確認してください。 |
| **指定された列が見つかりません** | CSVファイルの構造を確認し、正しい列名またはインデックスを指定してください。 |
| **空の値が多い場合** | CSVファイルのデータが正しい列に存在しているか確認してください。 |
| **翻訳が途中で止まる** | DeepL APIのリクエスト制限を超えていないか確認してください。 |

---

## 📜 ライセンス
このプロジェクトは MIT ライセンスの下で公開されています。

---

## ⚖ 免責事項
このツールは現状のままで提供され、いかなる保証もありません。  
利用に際して発生した問題や損害について、開発者は責任を負いませんので、自己責任でご使用ください。

