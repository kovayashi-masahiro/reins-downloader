#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zumen_download.py — スプレッドシート「抽出物件」に載った物件の図面PDFだけを
REINS からピンポイントで取得する。※図面取得は会員プランにより課金される場合あり。

reins_downloader.py のログイン処理(Reins)を再利用する。

モード:
  python3 zumen_download.py --explore 100139902191 --headed
      1物件で「物件番号検索→図面」の画面を捕捉(スクショ+テキスト)。ダウンロードはしない。
      → 画面仕様を確認・selector調整するための偵察モード(無課金)。

  python3 zumen_download.py --one 100139902191 --headed --yes-charge
      1物件だけ実際に図面をダウンロード(課金テスト)。--yes-charge が無いと
      課金確認ダイアログで停止する。

  python3 zumen_download.py [--headed] [--limit N]
      スプレッドシート「抽出物件」の物件番号のうち、未取得(state未登録)のものを
      順に図面ダウンロード。毎朝の自動実行から呼ぶ本番モード。

デバッグ出力: logs/zumen_debug/ にスクショとページテキストを保存。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from reins_downloader import Reins, load_config, setup_logging, resolve_path, SCRIPT_DIR


# --------------------------------------------------------------------------- #
#  取得済み state（二重課金防止）
# --------------------------------------------------------------------------- #
def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
#  対象物件番号をスプレッドシート「抽出物件」から取得
# --------------------------------------------------------------------------- #
def load_target_bukken(cfg, log) -> list[dict]:
    """[{'no':..., 'category':..., 'area':...}, ...] を返す。"""
    z = cfg["zumen"]
    sa = resolve_path(z["service_account_json"])
    if not sa.exists():
        log.error("サービスアカウント鍵が見つかりません: %s", sa)
        return []
    try:
        import gspread
        gc = gspread.service_account(filename=str(sa))
        ss = gc.open_by_key(z["spreadsheet_id"])
        ws = ss.worksheet(z["tab"])
        rows = ws.get_all_records()  # ヘッダをキーにした dict のリスト
    except Exception as e:
        log.error("スプレッドシート読み込み失敗: %s", e)
        return []

    col = z.get("bukken_col", "物件番号")
    cats = set(z.get("categories") or [])
    out = []
    for r in rows:
        no = str(r.get(col, "")).strip()
        if not no:
            continue
        category = str(r.get("カテゴリ", "")).strip()
        if cats and category not in cats:
            continue
        out.append({"no": no, "category": category, "area": str(r.get("エリア", "")).strip()})
    return out


# --------------------------------------------------------------------------- #
#  図面取得ロジック（Reins を拡張）
# --------------------------------------------------------------------------- #
class ZumenGetter(Reins):
    def __init__(self, page, cfg, log, debug_dir: Path):
        super().__init__(page, cfg, log)
        self.debug_dir = debug_dir
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    # ---- デバッグ: 画面の状態をダンプ ----
    def dump(self, tag: str):
        try:
            self.page.screenshot(path=str(self.debug_dir / f"{tag}.png"), full_page=True)
        except Exception:
            pass
        try:
            (self.debug_dir / f"{tag}.txt").write_text(
                self.page.locator("body").inner_text(), encoding="utf-8")
        except Exception:
            pass

    def dump_form_fields(self, tag: str):
        """入力欄・ボタン・タブの一覧をJSONで書き出す（画面仕様の把握用）。"""
        info = {"inputs": [], "selects": [], "buttons": [], "tabs": [], "links": []}
        try:
            for el in self.page.query_selector_all("input"):
                info["inputs"].append({
                    "type": el.get_attribute("type"),
                    "name": el.get_attribute("name"),
                    "id": el.get_attribute("id"),
                    "placeholder": el.get_attribute("placeholder"),
                    "maxlength": el.get_attribute("maxlength"),
                    "aria-label": el.get_attribute("aria-label"),
                })
            for el in self.page.query_selector_all("select"):
                opts = [o.inner_text().strip() for o in el.query_selector_all("option")][:8]
                info["selects"].append({"name": el.get_attribute("name"), "id": el.get_attribute("id"), "options": opts})
            for el in self.page.query_selector_all("button, a[role=button]"):
                t = (el.inner_text() or "").strip()
                if t:
                    info["buttons"].append(t[:30])
            for el in self.page.query_selector_all("[role=tab]"):
                t = (el.inner_text() or "").strip()
                if t:
                    info["tabs"].append(t[:30])
            for el in self.page.query_selector_all("a"):
                t = (el.inner_text() or "").strip()
                if t and ("図面" in t or "詳細" in t or "物件" in t):
                    info["links"].append(t[:30])
        except Exception as e:
            info["error"] = str(e)
        (self.debug_dir / f"{tag}_fields.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        return info

    # ---- 物件番号検索の画面へ ----
    def goto_bukken_search(self):
        """右メニューの『物件番号検索』リンクから専用画面を開く。"""
        # まず売買検索画面（右メニューが出る画面）へ
        self.page.goto(self.cfg["search"]["page_url"], wait_until="networkidle", timeout=self.timeout)
        self.page.wait_for_timeout(1200)
        # 右メニューの「物件番号検索」をクリック
        try:
            link = self.page.get_by_text("物件番号検索", exact=True)
            if link.count() > 0:
                link.first.click()
                self.page.wait_for_load_state("networkidle", timeout=self.timeout)
                self.page.wait_for_timeout(1500)
        except Exception as e:
            self.log.warning("物件番号検索リンクのクリックに失敗: %s", e)

    def find_bukken_input(self):
        """物件番号1の入力欄を探す。専用画面は maxlength=12 のテキスト欄が並ぶ（先頭＝物件番号1）。"""
        # 0) maxlength=12 のテキスト入力の先頭（BootstrapVueでidは動的なため属性で特定）
        for el in self.page.query_selector_all("input[type='text'][maxlength='12']"):
            try:
                if el.is_visible():
                    return el
            except Exception:
                pass
        # 1) placeholder / aria-label / name に物件番号系
        for el in self.page.query_selector_all("input[type='text'], input:not([type]), textarea"):
            for attr in ("placeholder", "aria-label", "name", "id"):
                v = el.get_attribute(attr) or ""
                if "物件番号" in v or "bukken" in v.lower() or "bukkenNo" in v:
                    return el
        # 2) 画面内の可視テキスト入力が1つだけなら、それを採用
        visibles = []
        for el in self.page.query_selector_all("input[type='text'], input:not([type]), textarea"):
            try:
                if el.is_visible():
                    visibles.append(el)
            except Exception:
                pass
        if len(visibles) == 1:
            return visibles[0]
        return None

    def explore(self, bukken_no: str):
        """偵察: 物件番号検索の画面を捕捉し、可能なら検索まで実行してダンプ（無課金）。"""
        self.log.info("[explore] ログイン中…")
        self.login()
        self.log.info("[explore] 検索画面へ…")
        self.goto_bukken_search()
        self.dump("01_search_screen")
        fields = self.dump_form_fields("01_search_screen")
        self.log.info("[explore] inputs=%d selects=%d 検出。debugフォルダを確認: %s",
                      len(fields.get("inputs", [])), len(fields.get("selects", [])), self.debug_dir)

        inp = self.find_bukken_input()
        if not inp:
            self.log.warning("[explore] 物件番号の入力欄を自動特定できませんでした。"
                             "01_search_screen.png と 01_search_screen_fields.json を確認してください。")
            return
        self.log.info("[explore] 物件番号欄を検出。%s を入力して検索します…", bukken_no)
        inp.fill(bukken_no)
        self.page.wait_for_timeout(400)
        try:
            self.page.get_by_role("button", name=self.sel["search_button_text"], exact=True).first.click()
            self.page.wait_for_load_state("networkidle", timeout=self.timeout)
            self.page.wait_for_timeout(1500)
            self._dismiss_dialog()
        except Exception as e:
            self.log.warning("[explore] 検索クリックで例外: %s", e)
        self.dump("02_result_screen")
        self.dump_form_fields("02_result_screen")
        self.log.info("[explore] 完了。02_result_screen.png で図面ボタンの位置を確認してください。"
                      "（このモードではダウンロードしません）")

    def download_one(self, bukken_no: str, out_dir: Path, yes_charge: bool) -> bool:
        """1物件の図面PDFを取得。成功でTrue。"""
        self.goto_bukken_search()
        inp = self.find_bukken_input()
        if not inp:
            self.log.error("物件番号の入力欄が見つかりません（画面仕様が未確定）。--explore で確認してください。")
            return False
        inp.fill(bukken_no)
        self.page.wait_for_timeout(400)
        self.page.get_by_role("button", name=self.sel["search_button_text"], exact=True).first.click()
        self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        self.page.wait_for_timeout(1500)
        self._dismiss_dialog()

        # 行ごとの「図面」ボタン（exact=Trueで『図面一括取得』を除外）
        zumen_btn = None
        try:
            loc = self.page.get_by_role("button", name="図面", exact=True)
            if loc.count() > 0 and loc.first.is_visible():
                zumen_btn = loc.first
        except Exception:
            pass
        if zumen_btn is None:
            self.log.error("行の図面ボタンが見つかりません(%s)。図面なし物件か画面変更の可能性。", bukken_no)
            self.dump(f"nozumen_{bukken_no}")
            return False

        # 課金確認ダイアログを先読み判定（クリック後に出るケース）
        out_dir.mkdir(parents=True, exist_ok=True)
        got_path = None

        # ダウンロード／新規タブPDF の両対応
        ctx = self.page.context
        new_pages = []
        ctx.on("page", lambda p: new_pages.append(p))

        try:
            with self.page.expect_download(timeout=12000) as dl_info:
                zumen_btn.click()
                self.page.wait_for_timeout(1000)
                # 課金確認モーダルが出たら
                if self._dialog_visible():
                    msg = ""
                    try:
                        msg = self.page.locator(".modal.show").first.inner_text()[:150]
                    except Exception:
                        pass
                    self.dump(f"charge_dialog_{bukken_no}")
                    if not yes_charge:
                        self.log.warning("課金確認ダイアログを検出。--yes-charge 無しのため中止します:\n%s", msg)
                        self._dismiss_dialog()
                        return False
                    self.log.info("課金確認にOKします: %s", msg)
                    self.page.get_by_role("button", name=self.sel["dialog_ok_text"]).first.click()
            dl = dl_info.value
            ext = Path(dl.suggested_filename).suffix or ".pdf"
            got_path = out_dir / f"{bukken_no}{ext}"
            dl.save_as(str(got_path))
        except PWTimeout:
            # ダウンロードイベントが来ない＝新規タブでPDF表示の可能性
            self.page.wait_for_timeout(2000)
            for p in list(new_pages):
                try:
                    url = p.url
                    if url and (".pdf" in url.lower() or "zumen" in url.lower() or "pdf" in url.lower()):
                        # 新規タブのPDFを保存
                        body = p.context.request.get(url).body()
                        got_path = out_dir / f"{bukken_no}.pdf"
                        got_path.write_bytes(body)
                        break
                except Exception:
                    continue
            if got_path is None:
                self.log.warning("図面の取得方法を確定できませんでした(%s)。charge/newtab のダンプを確認。", bukken_no)
                self.dump(f"dlfail_{bukken_no}")
                # 新規タブがあれば内容ダンプ
                for i, p in enumerate(new_pages):
                    try:
                        p.screenshot(path=str(self.debug_dir / f"newtab_{bukken_no}_{i}.png"))
                    except Exception:
                        pass
                return False

        if got_path and got_path.exists():
            self.log.info("図面を保存: %s (%d bytes)", got_path, got_path.stat().st_size)
            return True
        return False


# --------------------------------------------------------------------------- #
#  メイン
# --------------------------------------------------------------------------- #
def run(args):
    cfg = load_config(Path(args.config))
    log = setup_logging(SCRIPT_DIR / "logs")
    log.info("=" * 50)
    log.info("REINS 図面ダウンロード 開始")

    z = cfg["zumen"]
    debug_dir = SCRIPT_DIR / "logs" / "zumen_debug"
    today_dir = resolve_path(cfg["output"]["base_dir"]) / f"{datetime.now():%Y-%m-%d}" / z.get("out_subdir", "図面")
    state_path = resolve_path(z["state_file"])
    state = load_state(state_path)

    headless = not args.headed and not args.explore  # explore/testは表示推奨

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        g = ZumenGetter(page, cfg, log, debug_dir)
        try:
            # 偵察モード
            if args.explore:
                g.explore(args.explore)
                return 0

            g.login()

            # 単発テスト
            if args.one:
                ok = g.download_one(args.one, today_dir, yes_charge=args.yes_charge)
                if ok:
                    state[args.one] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_state(state_path, state)
                return 0 if ok else 1

            # 本番バッチは enabled=true のときだけ（誤課金防止の安全弁）
            if not z.get("enabled", False):
                log.warning("zumen.enabled が false のため本番バッチをスキップしました。"
                            "1件テスト(--one)で確認後、config.yaml の zumen.enabled を true にしてください。")
                return 0

            # 本番: スプレッドシートの物件番号で未取得だけ
            targets = load_target_bukken(cfg, log)
            log.info("スプレッドシート対象: %d件", len(targets))
            todo = [t for t in targets if t["no"] not in state]
            log.info("うち未取得(新着): %d件", len(todo))

            limit = args.limit if args.limit is not None else z.get("daily_limit", 0)
            if limit and limit > 0:
                todo = todo[:limit]
                log.info("本日の上限 %d件に制限", limit)

            got = 0
            for t in todo:
                log.info("▼ 図面取得: %s (%s %s)", t["no"], t["category"], t["area"])
                if g.download_one(t["no"], today_dir, yes_charge=True):
                    state[t["no"]] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_state(state_path, state)  # 1件ごとに保存(途中終了に強く)
                    got += 1
                page.wait_for_timeout(800)
            log.info("完了。図面取得 %d件。保存先: %s", got, today_dir)
            return 0
        except Exception as e:
            log.exception("エラー: %s", e)
            try:
                page.screenshot(path=str(SCRIPT_DIR / "zumen_error.png"), full_page=True)
            except Exception:
                pass
            return 1
        finally:
            ctx.close()
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="REINS 図面ダウンロード（抽出物件のみ）")
    ap.add_argument("--config", default=str(SCRIPT_DIR / "config.yaml"))
    ap.add_argument("--headed", action="store_true", help="ブラウザを表示")
    ap.add_argument("--explore", metavar="物件番号", help="偵察: 画面を捕捉のみ(無課金)")
    ap.add_argument("--one", metavar="物件番号", help="1物件だけ実際に取得(テスト)")
    ap.add_argument("--yes-charge", action="store_true", help="課金確認ダイアログにOKする")
    ap.add_argument("--limit", type=int, default=None, help="本番モードの取得上限件数")
    args = ap.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
