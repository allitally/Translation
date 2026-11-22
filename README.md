# 英語テキストの日本語変換

英語のテキストファイルを読み、OpenAI互換のチャットAPIへ送って日本語に変換します。接続先のURLを `.config` に書けば、OpenAI以外の互換サービスでも同じコマンドで使えます。

Python 3.10以降で動作します。追加のパッケージは不要です。

## 準備

`.config.example` を、`translate.py` と同じディレクトリの `.config` にコピーして値を記入します。

```
URL=https://api.openai.com/v1
API=sk-...
MODEL=gpt-4o-mini
```

| キー | 内容 |
| --- | --- |
| `URL` | チャットAPIのベースアドレス。末尾が `/chat/completions` でなければ自動で付けます。 |
| `API` | そのサービスのAPIキー。リクエストの `Authorization: Bearer` に使います。 |
| `MODEL` | 接続先が受け付けるモデル名。 |

`#` で始まる行はコメントです。値を引用符で囲んでも読み取れます。キーの大文字と小文字は区別しません。

`.config` はGitの管理対象外です。APIキーはこのファイルだけに書いてください。

### 接続先の例

| サービス | `URL` |
| --- | --- |
| OpenAI | `https://api.openai.com/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Ollama | `http://localhost:11434/v1` |
| LM Studio | `http://localhost:1234/v1` |

`MODEL` は各サービスで有効な名前にします。OpenAIの例は `gpt-4o-mini`、Ollamaではローカルに取得済みのモデル名です。

## 実行

入力ファイルはUTF-8です。

```
python translate.py document.txt
```

日本語は `document.ja.txt` に書き出されます。拡張子がない入力は `.ja.txt` になります。

出力先を指定する場合:

```
python translate.py document.txt -o result.txt
```

作業ディレクトリがスクリプトの場所と違っても、設定は `translate.py` の隣にある `.config` を読みます。

### オプション

| オプション | 内容 |
| --- | --- |
| `-o`、`--output` | 日本語の出力ファイル。省略時は入力名に `.ja` を付けたファイル。 |
| `--config` | 設定ファイルのパス。既定はスクリプトと同じディレクトリの `.config`。 |
| `--timeout` | HTTPタイムアウト秒。既定は 180。 |

## 送信内容

ファイル本文は、次の指示のあとに続けて1回のチャット要求として送ります。

```
添付の英語テキストを日本語に変換してください。意味と段落構成を保ち、変換結果だけを返してください。
```

応答の翻訳文だけをUTF-8で保存します。長い文書は、接続先モデルの入力上限を超えるとAPIがエラーを返します。
