from django.test import Client, SimpleTestCase

from . import db


class DbBrowserTests(SimpleTestCase):
    def test_tables_are_detected(self):
        names = [table.name for table in db.get_tables()]
        self.assertIn("passages", names)
        self.assertNotIn("reuse_notes", names)

    def test_passage_list_and_search_pages_render(self):
        client = Client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ようこそ")
        self.assertContains(response, "今日はどんな英文で学習しますか？")
        self.assertContains(response, "/read/")
        self.assertContains(response, "学習サポート広告")
        self.assertContains(response, "英文一覧の途中に表示する広告枠です")
        self.assertNotContains(response, "reuse_notes")

        self.assertEqual(client.get("/?q=design").status_code, 200)
        filtered_response = client.get("/?q=関西大学 design&level_tag=[KKD-MARCH]&word_min=900&word_max=1000")
        self.assertEqual(filtered_response.status_code, 200)
        self.assertContains(filtered_response, "検索結果")
        self.assertContains(filtered_response, "[KKD-MARCH]")

        search_response = client.get("/search/?q=design")
        self.assertEqual(search_response.status_code, 200)
        self.assertNotContains(search_response, "reuse_notes")

    def test_row_detail_renders_for_existing_passage(self):
        first_page = db.list_rows("passages", page=1, per_page=1)
        self.assertTrue(first_page["rows"])

        passage_id = first_page["rows"][0]["id"]
        read_response = Client().get(f"/passages/{passage_id}/read/")
        self.assertEqual(read_response.status_code, 200)
        self.assertContains(read_response, "読み終えたので分析へ進む")
        self.assertContains(read_response, "読解開始前に表示する広告枠です")
        self.assertContains(read_response, "英文読解を終えた後に表示する広告枠です")
        self.assertNotContains(read_response, "文法分析")
        self.assertNotContains(read_response, "日本語訳")

        response = Client().get(f"/passages/{passage_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "文法分析")
        self.assertContains(response, "論理関係")
        self.assertContains(response, "分析画面下部の広告枠")
        self.assertContains(response, "分析セクションの途中に表示する広告枠です")
        self.assertNotContains(response, "reuse_notes")
