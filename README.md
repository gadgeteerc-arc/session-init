# session-init

Hermes 用プラグイン。セッション開始時に指定ファイルを先読みし、初回ターンのユーザーメッセージにコンテキストとして注入します。

## 仕組み

- `on_session_start` でバックグラウンドスレッドを起動し、ファイルを先読み
- `pre_llm_call` の初回ターンでキャッシュ済みコンテキストを注入
- 注入先はユーザーメッセージ（システムプロンプトではない）なので、プロンプトキャッシュのプレフィックスを壊さない

## インストール

```bash
# 1. プラグインフォルダに配置
cp -r session-init ~/.hermes/plugins/session-init

# 2. 有効化
hermes plugins enable session-init

# 3. Hermes を再起動（再起動しないとフックが登録されない）
```

## 自分の環境に合わせて書き換える箇所

`__init__.py` を開いて以下の2箇所を編集してください。

### 1. `_HERMES_HOME`（任意）

```python
_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / "hermes"))
```

デフォルトは `~/hermes`。環境変数 `HERMES_HOME` で上書きできます。

### 2. `_UNIQUE_FILES`（必須）

```python
# 読み込ませたいファイルを HERMES_HOME からの相対パスで列挙してください
# 例:
#_UNIQUE_FILES = [
#    "PERSONA.md",
#    "PROFILE.md",
#]
_UNIQUE_FILES: list[str] = []
```

`_HERMES_HOME` からの相対パスでファイルを列挙します。空のままだと日時のみ注入されます。

## 既知の制約

| 制約 | 内容 |
|------|------|
| **JSTナイーブ問題** | `datetime.now()` はシステムのローカル時刻を使用。タイムゾーン情報（tzinfo）は付かないため、UTC環境で動かす場合は JST とのずれに注意 |
| **文字列結合** | コンテキストはファイル内容を `\n\n` で単純結合。マークダウン構造の崩れなどは呼び出し側で処理してください |
| **再起動必須** | プラグインの有効化・ファイル変更後は Hermes の再起動が必要。ホットリロードには対応していません |

## ファイル構成

```
session-init/
├── __init__.py   # プラグイン本体
└── plugin.yaml   # マニフェスト
```
