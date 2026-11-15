# IaC scaffold 検証ステータス（2026-11-13）

| チェック | 結果 |
|---|---|
| 既存Compose構成/サービス分離 | OK（`python scripts/check_compose.py`） |
| FastAPI backend | 21テスト成功 |
| FastAPI inference | 15テスト成功 |
| 評価スクリプト | 5テスト成功 |
| Terraformの主要リソース/設定ファイルの存在・参照 | 静的チェックOK |
| `.tf` の括弧・文字列の基本的なバランス | 静的チェックOK（Terraform構文検証の代用にはならない） |
| `terraform fmt`, `terraform validate`, `terraform plan` | **未実施**（実行環境にTerraform CLI/プロバイダなし） |
| AWS/GCPでのapply・モデル入りOCI imageビルド・統合試験 | **未実施** |

このIaCは、**クラウドでのサービス分離・責務・必要な設定の説明を目的とするモック/スキャフォールド**です。本番対応済みという意味ではありません。AWS/GCP各フォルダの`DEPLOY_CHECKLIST.md`を使ってギャップを確認してください。
