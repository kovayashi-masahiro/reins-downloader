#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REINS 新着・更新物件 自動ダウンロードツール
==========================================

REINS IP (https://system.reins.jp) にログインし、ワンタッチ検索に保存された
「自動：」で始まる検索条件を順に実行して、
  - 物件一覧 (CSV / Excel)
  - （任意）各物件のPDF図面（※会員プランにより課金される場合があります）
を保存します。重複は自動で除外し、価格・取引状況の変化（更新）も検知します。

使い方:
    python reins_downloader.py             # 通常実行（毎日これを動かす）
    python reins_downloader.py --headed     # 今回だけブラウザを表示して実行
    python reins_downloader.py --list-only  # 保存済み検索条件の一覧だけ表示して終了

※ REINSは会員制システムです。ご自身の正規アカウントでのみ利用してください。
※ PDF図面の取得は config.yaml の pdf.download を true にした場合のみ行います（課金注意）。

このツールは 2026 年時点の REINS東日本 IP 画面に合わせて作成しています。
画面が変更され項目がずれた場合は config.yaml の selectors を調整してください。
"""

import argparse
import csv
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML が必要です。`pip install pyyaml` を実行してください。")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("Playwright が必要です。README の手順でインストールしてください。")

SCRIPT_DIR = Path(__file__).resolve().parent

# 物件番号（12桁）
BUKKEN_NO = re.compile(r"(?<!\d)\d{12}(?!\d)")
PRICE = re.compile(r"[\d,]+(?:\.\d+)?\s*万円")
PREF = re.compile(r"(東京都|北海道|(?:京都|大阪)府|[^\s]{2,3}県)")
CHIKUNEN = re.compile(r"\d{4}\s*年（[^）]*）\s*\d{1,2}\s*月")
PHONE = re.compile(r"0\d{1,3}[-\d]{7,12}")
TATEMONO_M2 = re.compile(r"[\d,]+(?:\.\d+)?\s*㎡")
TORIHIKI_TAIYO = ("専属専任", "専属", "専任", "一般", "売主", "代理")
TORIHIKI_JOKYO = ("公開中", "申込あり", "書面による購入申込みあり", "一時停止", "売主都合で一時紹介停止中")
SHUMOKU = ("マンション", "アパート", "ビル", "店舗付住宅", "住宅付店舗", "寮",
           "戸建", "一戸建", "土地", "店舗", "事務所", "倉庫", "工場", "その他")


# --------------------------------------------------------------------------- #
#  設定・ユーティリティ
# --------------------------------------------------------------------------- #
def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(
            f"設定ファイルが見つかりません: {path}\n"
            "config.example.yaml を config.yaml にコピーして編集してください。"
        )
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logfile = log_dir / f"reins_{datetime.now():%Y%m%d}.log"
    logger = logging.getLogger("reins")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_path(base: str) -> Path:
    p = Path(base)
    return p if p.is_absolute() else (SCRIPT_DIR / p)


# --------------------------------------------------------------------------- #
#  結果一覧テキストのパース
# --------------------------------------------------------------------------- #
def parse_records(body_text: str) -> list:
    """結果一覧のテキストを物件番号単位の辞書リストに変換する。"""
    lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
    # 物件番号の行インデックス
    idxs = [i for i, ln in enumerate(lines) if BUKKEN_NO.fullmatch(ln)]
    records = []
    for k, start in enumerate(idxs):
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        block = lines[start:end]
        # ブロック末尾のボタン等を除去
        block = [b for b in block if b not in ("概要", "詳細", "図面")]
        rec = parse_block(block)
        if rec:
            records.append(rec)
    return records


def parse_block(block: list) -> dict:
    if not block:
        return {}
    no = block[0]
    text = "\n".join(block)

    # 種目（物件番号の次の、既知の種目語を含む行）
    shumoku = ""
    for ln in block[1:4]:
        if any(s in ln for s in SHUMOKU):
            shumoku = ln
            break

    price = ""
    m = PRICE.search(text)
    if m:
        price = m.group().replace(" ", "")

    addr = ""
    for ln in block:
        if PREF.match(ln) and ("市" in ln or "区" in ln or "町" in ln or "村" in ln or "郡" in ln):
            addr = ln
            break

    chiku = ""
    m = CHIKUNEN.search(text)
    if m:
        chiku = re.sub(r"\s+", "", m.group())

    # 沿線駅（「線」を含み、駅名がある行）
    ensen = ""
    for ln in block:
        if "線" in ln and "用途" not in ln and len(ln) < 30:
            ensen = ln
            break

    # 交通（徒歩/バス/車 ... 分・km）
    kotsu = ""
    for ln in block:
        if re.search(r"(徒歩|バス|車).*(分|km)", ln):
            kotsu = ln
            break

    taiyo = next((t for t in TORIHIKI_TAIYO if t in text), "")
    jokyo = next((j for j in TORIHIKI_JOKYO if j in text), "")
    owner_change = "オーナーチェンジ" if "オーナーチェンジ" in text else ""

    # 面積（㎡行の位置を特定：1つ目=土地面積, 2つ目=建物面積）
    m2_idx = [i for i, ln in enumerate(block) if TATEMONO_M2.fullmatch(ln)]
    tochi_m2 = block[m2_idx[0]] if len(m2_idx) >= 1 else ""
    tatemono_m2 = block[m2_idx[1]] if len(m2_idx) >= 2 else ""

    # 用途地域＝建物面積(2つ目の㎡)の直前行 / 建物名＝建物面積の直後行
    yoto, tatemono_name = "", ""
    if len(m2_idx) >= 2:
        bi = m2_idx[1]
        if bi - 1 >= 0:
            yoto = block[bi - 1]
        if bi + 1 < len(block):
            nxt = block[bi + 1]
            # 「-」や取引状況が続く場合は建物名なし
            if nxt == "-" or nxt in TORIHIKI_JOKYO:
                tatemono_name = ""
            else:
                tatemono_name = nxt

    # 電話番号（最後に出現するもの）
    phones = PHONE.findall(text)
    phone = phones[-1] if phones else ""

    # 商号（電話番号の直前行。直前が築年月ならその前の行）
    shogo = ""
    phone_idx = next((i for i, ln in enumerate(block) if phone and phone in ln), None)
    if phone_idx is not None and phone_idx > 0:
        prev = block[phone_idx - 1]
        if CHIKUNEN.search(prev) and phone_idx - 2 >= 0:
            shogo = block[phone_idx - 2]
        else:
            shogo = prev

    return {
        "物件番号": no,
        "種目": shumoku,
        "取引態様": taiyo,
        "取引状況": jokyo,
        "オーナーチェンジ": owner_change,
        "価格": price,
        "用途地域": yoto,
        "土地面積": tochi_m2,
        "建物面積": tatemono_m2,
        "所在地": addr,
        "建物名": tatemono_name,
        "沿線駅": ensen,
        "交通": kotsu,
        "商号": shogo,
        "築年月": chiku,
        "電話番号": phone,
    }


CSV_COLUMNS = ["検索条件", "物件番号", "種目", "取引態様", "取引状況", "オーナーチェンジ",
               "価格", "用途地域", "土地面積", "建物面積", "所在地", "建物名", "沿線駅",
               "交通", "商号", "築年月", "電話番号", "取得日時"]


def record_signature(rec: dict) -> str:
    """更新検知用の署名（価格・取引状況が変われば別物として扱う）。"""
    return f"{rec.get('価格','')}|{rec.get('取引状況','')}|{rec.get('オーナーチェンジ','')}"


# --------------------------------------------------------------------------- #
#  REINS 操作
# --------------------------------------------------------------------------- #
class Reins:
    def __init__(self, page, cfg, log):
        self.page = page
        self.cfg = cfg
        self.log = log
        self.sel = cfg.get("selectors", {})
        self.timeout = cfg["run"].get("timeout_seconds", 30) * 1000

    def login(self):
        c = self.cfg["login"]
        self.log.info("ログインページを開いています…")
        self.page.goto(c["url"], wait_until="networkidle", timeout=self.timeout)
        self.page.wait_for_timeout(2500)
        self.page.query_selector(self.sel["login_user_id"]).fill(c["user_id"])
        self.page.query_selector(self.sel["login_password"]).fill(c["password"])

        if self.cfg.get("agree_compliance", True):
            if self._ensure_agree_checked():
                self.log.info("規程・ガイドライン遵守のチェックを入れました。")
            else:
                self.log.warning("遵守チェックを自動でONにできませんでした。手動でチェックしてください。")

        self.page.get_by_role("button", name=self.sel["login_button_text"]).click()
        self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        self.page.wait_for_timeout(2500)

        # まだログイン画面にいる場合（チェック漏れ等）は、もう一度チェックして再試行
        if "login" in self.page.url and self.cfg.get("agree_compliance", True):
            self.log.info("ログインが完了していないため再試行します…")
            self._ensure_agree_checked()
            self.page.wait_for_timeout(500)
            try:
                self.page.get_by_role("button", name=self.sel["login_button_text"]).click()
                self.page.wait_for_load_state("networkidle", timeout=self.timeout)
                self.page.wait_for_timeout(2500)
            except Exception:
                pass

        if "GKG003100" in self.page.url or ("main/KG" in self.page.url and "login" not in self.page.url):
            self.log.info("ログイン成功。")
        else:
            self.log.warning("ログイン後の遷移を確認できません。現在URL: %s", self.page.url)

    def _ensure_agree_checked(self) -> bool:
        """「規程及びガイドラインを遵守します」チェックを確実にONにする。"""
        label = self.sel["login_agree_label"]
        # 1) ラベルに紐づくinputを直接check
        try:
            cb = self.page.get_by_label(label)
            if cb.count() > 0:
                if not cb.first.is_checked():
                    cb.first.check(timeout=3000)
                if cb.first.is_checked():
                    return True
        except Exception:
            pass
        # 2) ラベル文言（テキスト）をクリックしてトグル
        try:
            self.page.get_by_text(label, exact=False).first.click(timeout=3000)
            self.page.wait_for_timeout(300)
        except Exception:
            pass
        if self._agree_is_checked(label):
            return True
        # 3) 画面上のチェックボックスを順に試す（保存用チェックは除外して検証）
        try:
            for el in self.page.query_selector_all("input[type='checkbox']"):
                try:
                    if not el.is_checked():
                        el.check(timeout=1500)
                except Exception:
                    try:
                        el.click(timeout=1500)
                    except Exception:
                        pass
                if self._agree_is_checked(label):
                    return True
        except Exception:
            pass
        return self._agree_is_checked(label)

    def _agree_is_checked(self, label) -> bool:
        try:
            cb = self.page.get_by_label(label)
            return cb.count() > 0 and cb.first.is_checked()
        except Exception:
            return False

    def open_search(self):
        self.page.goto(self.cfg["search"]["page_url"], wait_until="networkidle", timeout=self.timeout)
        self.page.wait_for_timeout(1500)
        # ワンタッチ検索が折りたたまれている場合は展開
        try:
            toggle = self.page.get_by_text("検索条件を表示", exact=False)
            if toggle.count() > 0 and toggle.first.is_visible():
                toggle.first.click()
                self.page.wait_for_timeout(800)
        except Exception:
            pass

    def saved_search_select(self):
        """ワンタッチ検索の保存条件selectを返す（最初に『自動：』を含むもの）。"""
        for sel in self.page.query_selector_all("select"):
            opts = sel.query_selector_all("option")
            labels = [o.inner_text().strip() for o in opts]
            if any("自動" in lb for lb in labels):
                return sel, labels
        return None, []

    def list_saved_searches(self):
        _, labels = self.saved_search_select()
        prefix = self.cfg["search"]["saved_search_prefix"]
        return [lb for lb in labels if prefix in lb]

    def run_saved_search(self, label: str) -> str:
        """保存条件を読み込み→検索し、結果一覧ページの本文テキストを返す。"""
        sel_el, _ = self.saved_search_select()
        if sel_el is None:
            raise RuntimeError("保存済み検索条件のselectが見つかりません。")
        # ラベルで選択（ElementHandle側のselect_optionを使う）
        sel_el.select_option(label=label)
        self.page.wait_for_timeout(500)
        # 読込
        self.page.get_by_role("button", name=self.sel["saved_search_load_text"]).first.click()
        self.page.wait_for_timeout(800)
        self._dismiss_dialog(wait_appear=True)   # 「読込みました」OKを確実に閉じる
        self.page.wait_for_timeout(400)
        # 検索（ダイアログが消えてから押す）
        self.page.get_by_role("button", name=self.sel["search_button_text"], exact=True).first.click()
        self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        self.page.wait_for_timeout(1500)
        # ダイアログをチェック
        if self._dialog_visible():
            msg = self._dialog_text()
            # 「500件を超えています」ダイアログの場合は OK して続行
            if "500件を超えています" in msg or "超えています" in msg:
                self.log.info("検索結果が500件超過。続行します...")
                self._dismiss_dialog()
                self.page.wait_for_timeout(1500)
            else:
                # その他のエラーはスキップ
                self._dismiss_dialog()
                self.log.warning("検索でエラー: %s", msg[:80])
                return ""
        return self.page.locator("body").inner_text()

    def scrape_all_pages(self, search_label: str) -> list:
        """結果一覧の全タブ・全ページをスクレイピングして辞書リストを返す。"""
        all_recs, seen = [], set()
        max_pages = self.cfg["run"].get("max_pages", 20)
        # タブ（種別ごと）を順に
        tabs = self.page.get_by_role("tab")
        n_tabs = tabs.count()
        tab_idx = 0
        while True:
            if n_tabs > 1:
                try:
                    tabs = self.page.get_by_role("tab")
                    if tab_idx >= tabs.count():
                        break
                    tabs.nth(tab_idx).click()
                    self.page.wait_for_timeout(1200)
                except Exception:
                    break
            # ページ送り
            for _ in range(max_pages):
                body = self.page.locator("body").inner_text()
                for rec in parse_records(body):
                    if rec["物件番号"] in seen:
                        continue
                    seen.add(rec["物件番号"])
                    rec["検索条件"] = search_label
                    rec["取得日時"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    all_recs.append(rec)
                if not self._goto_next_page():
                    break
            tab_idx += 1
            if n_tabs <= 1 or tab_idx >= n_tabs:
                break
        return all_recs

    def download_pdfs(self, out_dir: Path, search_label: str) -> int:
        """図面一括取得（※課金）。selectしてボタンを押し、ダウンロードを保存。"""
        saved = 0
        try:
            self.page.get_by_role("button", name=self.sel["select_all_text"]).first.click()
            self.page.wait_for_timeout(500)
            with self.page.expect_download(timeout=self.timeout) as dl_info:
                self.page.get_by_role("button", name=self.sel["bulk_pdf_text"]).first.click()
            dl = dl_info.value
            safe = re.sub(r"[\\/:*?\"<>|]", "_", search_label)
            dest = out_dir / f"{safe}_{dl.suggested_filename}"
            dl.save_as(str(dest))
            saved += 1
            self.log.info("PDFを保存: %s", dest.name)
        except PWTimeout:
            self.log.warning("図面一括取得のダウンロードを確認できませんでした（課金確認画面が出る場合があります）。")
        except Exception as e:
            self.log.warning("図面取得をスキップ: %s", e)
        return saved

    # -- ダイアログ補助（REINSの画面内モーダル） -- #
    def _dialog_visible(self) -> bool:
        try:
            return self.page.get_by_role("button", name=self.sel["dialog_ok_text"]).count() > 0
        except Exception:
            return False

    def _dialog_text(self) -> str:
        try:
            return self.page.locator("text=エラー").first.inner_text()
        except Exception:
            return ""

    def _dismiss_dialog(self, wait_appear=False):
        try:
            ok = self.page.get_by_role("button", name=self.sel["dialog_ok_text"])
            if wait_appear:
                try:
                    ok.first.wait_for(state="visible", timeout=6000)
                except Exception:
                    pass
            # 連続でダイアログが出る場合に備えて数回試行
            for _ in range(3):
                if ok.count() > 0 and ok.first.is_visible():
                    ok.first.click()
                    self.page.wait_for_timeout(600)
                    try:
                        ok.first.wait_for(state="hidden", timeout=4000)
                    except Exception:
                        pass
                else:
                    break
        except Exception:
            pass

    def _goto_next_page(self) -> bool:
        try:
            nxt = self.page.get_by_role("menuitem", name=re.compile("next", re.I))
            if nxt.count() > 0 and nxt.first.is_enabled():
                nxt.first.click()
                self.page.wait_for_timeout(1200)
                return True
        except Exception:
            pass
        return False


# --------------------------------------------------------------------------- #
#  出力
# --------------------------------------------------------------------------- #
def write_csv(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)


def write_xlsx(path: Path, records: list, log):
    try:
        from openpyxl import Workbook
    except ImportError:
        log.warning("openpyxl 未導入のため Excel 出力をスキップ（pip install openpyxl）。")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "新着更新物件"
    ws.append(CSV_COLUMNS)
    for r in records:
        ws.append([r.get(c, "") for c in CSV_COLUMNS])
    wb.save(str(path))


# --------------------------------------------------------------------------- #
#  メイン
# --------------------------------------------------------------------------- #
def run(cfg, log, headed, list_only):
    out_base = resolve_path(cfg["output"]["base_dir"])
    today_dir = out_base / f"{datetime.now():%Y-%m-%d}"
    state_path = resolve_path(cfg["run"]["state_file"])
    state = load_state(state_path)

    headless = cfg["run"].get("headless", True) and not headed and not list_only

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        reins = Reins(page, cfg, log)
        try:
            reins.login()
            reins.open_search()

            saved = reins.list_saved_searches()
            log.info("対象の保存済み検索条件（『%s』付き）: %d件",
                     cfg["search"]["saved_search_prefix"], len(saved))
            for s in saved:
                log.info("  - %s", s)
            if list_only:
                return 0
            if not saved:
                log.warning("対象の保存条件がありません。REINSで『自動：…』の検索条件を保存してください。")
                return 0

            new_records = []
            pdf_count = 0
            for label in saved:
                log.info("▼ 実行: %s", label)
                body = reins.run_saved_search(label)
                if not body:
                    reins.open_search()
                    continue
                recs = reins.scrape_all_pages(label)
                log.info("   %d件ヒット", len(recs))

                # 新着・更新のみ抽出（物件番号＋署名で判定）
                fresh = []
                for r in recs:
                    key = r["物件番号"]
                    sig = record_signature(r)
                    if state.get(key) != sig:
                        state[key] = sig
                        fresh.append(r)
                log.info("   うち新着・更新: %d件", len(fresh))
                new_records.extend(fresh)

                # PDF図面（任意・課金）
                if cfg.get("pdf", {}).get("download", False) and fresh:
                    pdf_count += reins.download_pdfs(today_dir, label)

                reins.open_search()  # 次の条件のため検索画面へ戻る

            # 一覧出力
            if new_records:
                if cfg["output"].get("save_csv", True):
                    write_csv(today_dir / "新着更新物件.csv", new_records)
                if cfg["output"].get("save_xlsx", True):
                    write_xlsx(today_dir / "新着更新物件.xlsx", new_records, log)
                log.info("一覧を保存しました（%d件）: %s", len(new_records), today_dir)
            else:
                log.info("本日の新着・更新物件はありませんでした。")

            save_state(state_path, state)
            log.info("完了。PDF保存: %d件", pdf_count)
            return 0
        except Exception as e:
            log.exception("エラー: %s", e)
            try:
                page.screenshot(path=str(SCRIPT_DIR / "error_screenshot.png"), full_page=True)
                log.info("エラー時の画面を error_screenshot.png に保存しました。")
            except Exception:
                pass
            return 1
        finally:
            ctx.close()
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="REINS 新着・更新物件 自動ダウンロード")
    ap.add_argument("--config", default=str(SCRIPT_DIR / "config.yaml"))
    ap.add_argument("--headed", action="store_true", help="今回だけブラウザを表示")
    ap.add_argument("--list-only", action="store_true", help="対象の保存条件一覧だけ表示")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    log = setup_logging(SCRIPT_DIR / "logs")
    log.info("=" * 50)
    log.info("REINS 自動ダウンロード 開始")
    code = run(cfg, log, args.headed, args.list_only)
    log.info("終了 (code=%d)", code)
    sys.exit(code)


if __name__ == "__main__":
    main()
