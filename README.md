# 大学受験 英文DB

SQLiteファイル `english_examdb.sqlite` を使い、大学入試英文ごとに文法分析・論理関係・語彙などを閲覧するDjangoアプリケーションです。

## 起動方法

```powershell
python manage.py runserver 127.0.0.1:8000
```

ブラウザで `http://127.0.0.1:8000/` を開きます。

## Renderへのデプロイ

このリポジトリにはRender用の `render.yaml` を含めています。

1. GitHubにこのプロジェクトをpushします。
2. Renderで「New +」→「Blueprint」を選び、このリポジトリを接続します。
3. `render.yaml` が読み込まれるので、そのまま作成します。
4. デプロイ後、発行された `https://...onrender.com` のURLを開きます。

Renderでは以下が自動設定されます。

- `PYTHON_VERSION=3.13.13`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=.onrender.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://*.onrender.com`
- HTTPSリダイレクト、Secure Cookie、HSTS
- `DJANGO_SECRET_KEY` はRender側で自動生成

SQLiteファイル `english_examdb.sqlite` は読み取り用データとしてアプリに同梱しています。

## 機能

- 入試英文一覧から大学入試名をクリックして分析画面へ移動
- 英文本文・日本語訳の表示
- 出題意図、段落構成、論理関係、文法分析、重要語彙、コロケーションの表示
- 全テーブル横断検索
- ページネーション
- 分析項目の行詳細表示
- `reuse_notes` は画面と検索対象から除外
