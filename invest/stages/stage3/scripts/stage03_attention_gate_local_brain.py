#!/usr/bin/env python3
"""
Stage3 - Qualitative Axes Gate (LOCAL BRAIN ONLY)

목적
- Stage3 입력(JSONL)로부터 종목별 4축 정성점수
  (upside / downside_risk / bm_sector_fit / persistence)를 산출한다.
- 감성/주목도(attention/sentiment) 축은 운영점수에서 제거한다.
- remote/cloud 모델 사용을 금지하고, 로컬 정책 위반 시 FAIL-CLOSE 한다.

핵심 원칙
1) 4축 분리: upside/downside_risk/bm_sector_fit/persistence
2) 이중카운팅 방지: 축간 상관 임계치 + 단일축 가중치 cap
3) downstream 호환: qualitative_signal([-1,1]) 유지
4) DART 분석 결과는 별도 signal 출력(`outputs/signal/dart_event_signal.csv`)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

try:
    from invest.stages.run_manifest import write_run_manifest
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from run_manifest import write_run_manifest

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = Path(__file__).resolve().parents[1]
INPUT_DEFAULT = STAGE_ROOT / "inputs/stage2_text_meta_records.jsonl"
OUTPUT_DEFAULT = STAGE_ROOT / "outputs/features/stage3_qualitative_axes_features.csv"
DART_SIGNAL_OUTPUT_DEFAULT = STAGE_ROOT / "outputs/signal/dart_event_signal.csv"
SUMMARY_DEFAULT = STAGE_ROOT / "outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json"

UPSIDE_WORDS = {
    "성장", "개선", "확대", "수주", "계약", "흑자", "상향", "반등", "증가", "회복",
    "growth", "improve", "expand", "order", "beat", "upgrade", "strong", "recovery",
}
DOWNSIDE_WORDS = {
    "감소", "부진", "하락", "적자", "둔화", "악화", "소송", "분쟁", "유상증자", "리스크",
    "decline", "weak", "drop", "loss", "lawsuit", "dispute", "dilution", "downgrade", "risk",
}
PERSIST_POS_WORDS = {
    "지속", "장기", "반복", "연속", "누적", "중장기", "pipeline", "recurring", "long-term",
}
PERSIST_NEG_WORDS = {
    "일회성", "단기", "일시", "변동성", "불확실", "temporary", "one-off", "volatile", "uncertain",
}

EVENT_KEYWORDS = {
    "order": ["수주", "공급계약", "단일판매", "계약체결", "수주계약"],
    "rights_issue": ["유상증자", "증자", "전환사채", "cb", "bw", "신주발행"],
    "lawsuit": ["소송", "피소", "판결", "무죄", "항소", "가처분", "분쟁"],
    "guidance": ["가이던스", "실적전망", "전망치", "컨센서스", "잠정실적"],
}

RISK_ON_WORDS = {
    "완화", "인하", "랠리", "상승", "회복", "risk-on", "risk on", "soft landing", "stimulus", "easing",
}
RISK_OFF_WORDS = {
    "긴축", "인상", "침체", "전쟁", "관세", "하락", "위기", "리스크오프", "risk-off", "risk off", "recession", "conflict", "sanction",
}

SOURCE_RELIABILITY = {
    "dart": 1.00,
    "news_rss": 1.00,
    "news_rss_macro": 1.00,
    "text_telegram": 1.00,
    "text_blog": 1.00,
    "text_premium": 1.00,
    "text_image_map": 1.00,
    "text_images_ocr": 1.00,
    "other": 1.00,
}

SOURCE_BM_BASE = {
    "dart": 0.90,
    "news_rss": 0.76,
    "news_rss_macro": 0.65,
    "text_premium": 0.82,
    "text_blog": 0.66,
    "text_telegram": 0.60,
    "text_image_map": 0.58,
    "text_images_ocr": 0.58,
    "other": 0.55,
}

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

DUP_AXIS_CORR_THRESHOLD = 0.70
DUP_AXIS_WEIGHT_CAP = 0.25
DUP_AXIS_BASE_WEIGHTS = {
    "upside": 0.25,
    "downside": 0.25,
    "bm": 0.25,
    "persistence": 0.25,
}
DUP_AXIS_PRIORITY = {
    "downside": 4,
    "bm": 3,
    "persistence": 2,
    "upside": 1,
}


@dataclass
class Config:
    input_jsonl: Path
    output_csv: Path
    dart_signal_csv: Path
    summary_json: Path
    backend: str
    local_endpoint: str
    local_model: str
    bootstrap_empty_ok: bool


def _clip(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


def _fail(msg: str, code: int) -> None:
    print(f"[FAIL-CLOSE] {msg}", file=sys.stderr)
    raise SystemExit(code)


def _is_local_endpoint(endpoint: str) -> bool:
    ep = (endpoint or "").strip()
    if not ep:
        return False
    if ep.startswith("local://"):
        return True

    parsed = urlparse(ep)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").strip().lower()
    return host in LOCAL_HOSTS


def _assert_llama_endpoint_policy(endpoint: str) -> tuple[str, int]:
    parsed = urlparse((endpoint or "").strip())
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"}:
        _fail(f"llama_local endpoint는 http(s)만 허용: endpoint={endpoint}", 41)
    if host not in LOCAL_HOSTS:
        _fail(f"llama_local endpoint는 로컬 host만 허용: endpoint={endpoint}", 41)
    port = parsed.port or 11434
    return host or "127.0.0.1", port


def _assert_local_brain_guard(backend: str, endpoint: str, model_ref: str) -> None:
    if not _is_local_endpoint(endpoint):
        _fail(f"remote/cloud endpoint 금지 위반: endpoint={endpoint}", 41)

    banned = ["openai", "anthropic", "gemini", "bedrock", "claude", "gpt-"]
    low_model = (model_ref or "").strip().lower()
    if any(t in low_model for t in banned):
        _fail(f"remote/cloud model reference 금지 위반: model={model_ref}", 41)

    if backend not in {"keyword_local", "llama_local"}:
        _fail(f"지원하지 않는 backend(로컬 전용 아님): {backend}", 41)

    if backend == "llama_local":
        host, port = _assert_llama_endpoint_policy(endpoint)
        try:
            with socket.create_connection((host, port), timeout=1.2):
                pass
        except OSError as e:
            _fail(f"로컬 runtime 미가용(llama-server): {host}:{port} ({e})", 41)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[0-9A-Za-z가-힣_\-]+", text or "")]


def _normalize_text_for_dedup(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^0-9a-z가-힣 ]+", "", s)
    return s.strip()


def _text_fingerprint(text: str) -> str:
    norm = _normalize_text_for_dedup(text)
    return hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()


def _parse_kst_date(value: str) -> str:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return ""
        if ts.tzinfo is None:
            ts = ts.tz_localize("Asia/Seoul")
        else:
            ts = ts.tz_convert("Asia/Seoul")
    else:
        ts = ts.tz_convert("Asia/Seoul")
    return ts.date().isoformat()


def _source_family(source: str) -> str:
    s = (source or "").strip().lower()
    if s == "dart" or s.startswith("dart"):
        return "dart"
    if s.startswith("rss_macro:"):
        return "news_rss_macro"
    if s.startswith("rss:"):
        return "news_rss"
    if s.startswith("text/telegram"):
        return "text_telegram"
    if s.startswith("text/blog"):
        return "text_blog"
    if s.startswith("text/premium"):
        return "text_premium"
    if s.startswith("text/image_map"):
        return "text_image_map"
    if s.startswith("text/images_ocr"):
        return "text_images_ocr"
    return "other"


def _detect_event_flags(text: str, source_family: str) -> dict[str, bool]:
    flags = {k: False for k in EVENT_KEYWORDS.keys()}
    if source_family not in {"dart", "news_rss", "news_rss_macro", "text_premium", "text_blog", "text_telegram"}:
        return flags

    tl = (text or "").lower()
    for ev, kws in EVENT_KEYWORDS.items():
        flags[ev] = any(kw.lower() in tl for kw in kws)
    return flags


def _infer_macro_risk(text: str, source_family: str) -> tuple[float, int, int, bool]:
    if source_family not in {"news_rss", "news_rss_macro", "text_premium", "text_blog", "text_telegram"}:
        return 0.0, 0, 0, False

    tl = (text or "").lower()
    on = sum(1 for k in RISK_ON_WORDS if k in tl)
    off = sum(1 for k in RISK_OFF_WORDS if k in tl)
    if on + off == 0:
        return 0.0, 0, 0, False

    score = (on - off) / max(on + off, 1)
    return _clip(score, -1.0, 1.0), int(on), int(off), True


def _score_doc_axes(text: str, source_family: str, flags: dict[str, bool], macro_score: float, macro_has_signal: bool) -> dict[str, float]:
    toks = _tokenize(text)
    n_toks = len(toks)

    up_hits = sum(1 for t in toks if t in UPSIDE_WORDS)
    down_hits = sum(1 for t in toks if t in DOWNSIDE_WORDS)
    pers_pos = sum(1 for t in toks if t in PERSIST_POS_WORDS)
    pers_neg = sum(1 for t in toks if t in PERSIST_NEG_WORDS)

    polarity = (up_hits - down_hits) / max(up_hits + down_hits, 1)
    pers_balance = (pers_pos - pers_neg) / max(pers_pos + pers_neg, 1)

    upside = 50.0 + 24.0 * polarity + 10.0 * min(up_hits, 6) / 6.0
    downside = 50.0 - 20.0 * polarity + 12.0 * min(down_hits, 6) / 6.0

    # 이벤트 보정(방향성 분리)
    if flags.get("order", False):
        upside += 8.0
    if flags.get("guidance", False):
        upside += 4.0
    if flags.get("rights_issue", False):
        downside += 11.0
    if flags.get("lawsuit", False):
        downside += 10.0

    # 매크로 보정
    if macro_has_signal:
        upside += 8.0 * macro_score
        downside += 12.0 * (-macro_score)

    source_bm_base = 100.0 * SOURCE_BM_BASE.get(source_family, SOURCE_BM_BASE["other"])
    bm_sector_fit = source_bm_base
    if flags.get("order", False):
        bm_sector_fit += 4.0
    if flags.get("rights_issue", False) or flags.get("lawsuit", False):
        bm_sector_fit -= 6.0
    if macro_has_signal:
        bm_sector_fit += 6.0 * macro_score

    persistence = 45.0 + 18.0 * pers_balance + 12.0 * min(n_toks, 140) / 140.0
    if flags.get("order", False) or flags.get("guidance", False):
        persistence += 5.0
    if flags.get("rights_issue", False) or flags.get("lawsuit", False):
        persistence -= 4.0

    return {
        "upside_score_doc": _clip(upside, 0.0, 100.0),
        "downside_risk_score_doc": _clip(downside, 0.0, 100.0),
        "bm_sector_fit_score_doc": _clip(bm_sector_fit, 0.0, 100.0),
        "persistence_score_doc": _clip(persistence, 0.0, 100.0),
        "up_hits": float(up_hits),
        "down_hits": float(down_hits),
        "pers_pos_hits": float(pers_pos),
        "pers_neg_hits": float(pers_neg),
    }


def _weighted_mean(v: pd.Series, w: pd.Series) -> float:
    ws = float(w.sum())
    if ws <= 0:
        return float(v.mean()) if len(v) else 0.0
    return float((v * w).sum() / ws)


def _weighted_ratio(mask: pd.Series, w: pd.Series) -> float:
    ws = float(w.sum())
    if ws <= 0:
        return float(mask.mean()) if len(mask) else 0.0
    return float((mask.astype(float) * w).sum() / ws)


def _axis_corr_pairs(df: pd.DataFrame, cols: list[str], threshold: float) -> tuple[list[dict], pd.DataFrame]:
    if df.empty or len(df) < 3:
        return [], pd.DataFrame(index=cols, columns=cols, data=0.0)

    corr = df[cols].corr().fillna(0.0)
    pairs: list[dict] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i], cols[j]
            rho = float(corr.loc[a, b])
            if abs(rho) > threshold:
                pairs.append({"axis_a": a, "axis_b": b, "rho": rho})
    pairs.sort(key=lambda x: abs(float(x["rho"])), reverse=True)
    return pairs, corr


def _load_rows(cfg: Config) -> tuple[list[dict], list[dict], list[str], dict]:
    rows: list[dict] = []
    macro_docs: list[dict] = []
    errors: list[str] = []

    stats = {
        "docs_scanned": 0,
        "docs_loaded": 0,
        "docs_dedup_dropped": 0,
        "docs_skipped_macro_only": 0,
        "source_docs": {
            "dart": 0,
            "news_rss": 0,
            "news_rss_macro": 0,
            "text_telegram": 0,
            "text_blog": 0,
            "text_premium": 0,
            "text_image_map": 0,
            "text_images_ocr": 0,
            "other": 0,
        },
    }

    if not cfg.input_jsonl.exists():
        if cfg.bootstrap_empty_ok:
            return rows, macro_docs, errors, stats
        errors.append(f"input_missing:{cfg.input_jsonl}")
        return rows, macro_docs, errors, stats

    seen_fingerprint: set[str] = set()

    with cfg.input_jsonl.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            stats["docs_scanned"] += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"line={i}:json_decode_error:{e}")
                continue

            record_id = str(obj.get("record_id", "")).strip()
            published_at = str(obj.get("published_at", "")).strip()
            symbols = obj.get("symbols", [])
            text = str(obj.get("text", "")).strip()
            source = str(obj.get("source", "")).strip()
            source_family = _source_family(source)

            if not record_id:
                errors.append(f"line={i}:missing_record_id")
                continue
            if not published_at:
                errors.append(f"line={i}:missing_published_at")
                continue
            date_kst = _parse_kst_date(published_at)
            if not date_kst:
                errors.append(f"line={i}:invalid_published_at:{published_at}")
                continue
            if not isinstance(symbols, list) or len(symbols) == 0:
                errors.append(f"line={i}:symbols_must_be_non_empty_list")
                continue
            if not text:
                errors.append(f"line={i}:missing_text")
                continue

            fp = str(obj.get("content_fingerprint", "")).strip() or _text_fingerprint(text)
            if fp in seen_fingerprint:
                stats["docs_dedup_dropped"] += 1
                continue
            seen_fingerprint.add(fp)

            norm_symbols = []
            for s in symbols:
                ss = str(s).strip().upper()
                if not ss:
                    continue
                if ss == "__MACRO__":
                    continue
                norm_symbols.append(ss)

            flags = _detect_event_flags(text, source_family)
            macro_score, macro_on, macro_off, macro_has_signal = _infer_macro_risk(text, source_family)
            reliability = SOURCE_RELIABILITY.get(source_family, SOURCE_RELIABILITY["other"])
            doc_axes = _score_doc_axes(text, source_family, flags, macro_score, macro_has_signal)

            if macro_has_signal:
                macro_docs.append(
                    {
                        "date": date_kst,
                        "record_id": record_id,
                        "macro_score": macro_score,
                        "risk_on_cnt": macro_on,
                        "risk_off_cnt": macro_off,
                        "source_family": source_family,
                    }
                )

            if not norm_symbols:
                if source_family == "news_rss_macro":
                    stats["docs_skipped_macro_only"] += 1
                    stats["source_docs"][source_family] += 1
                    stats["docs_loaded"] += 1
                    continue
                errors.append(f"line={i}:symbols_all_empty")
                continue

            for sym in norm_symbols:
                rows.append(
                    {
                        "date": date_kst,
                        "symbol": sym,
                        "record_id": record_id,
                        "source": source,
                        "source_family": source_family,
                        "source_reliability": reliability,
                        "upside_score_doc": doc_axes["upside_score_doc"],
                        "downside_risk_score_doc": doc_axes["downside_risk_score_doc"],
                        "bm_sector_fit_score_doc": doc_axes["bm_sector_fit_score_doc"],
                        "persistence_score_doc": doc_axes["persistence_score_doc"],
                        "event_order": int(flags["order"]),
                        "event_rights_issue": int(flags["rights_issue"]),
                        "event_lawsuit": int(flags["lawsuit"]),
                        "event_guidance": int(flags["guidance"]),
                        "event_tagged": int(any(flags.values())),
                    }
                )

            stats["source_docs"][source_family] = stats["source_docs"].get(source_family, 0) + 1
            stats["docs_loaded"] += 1

    return rows, macro_docs, errors, stats


def _build_features(rows: list[dict], macro_docs: list[dict], backend: str) -> tuple[pd.DataFrame, dict]:
    cols = [
        "date",
        "symbol",
        "doc_count",
        "mention_count",
        "upside_score",
        "downside_risk_score",
        "risk_score",
        "bm_sector_fit_score",
        "persistence_score",
        "net_edge_score",
        "source_diversity_ratio",
        "source_reliability_mean",
        "dart_doc_count",
        "news_doc_count",
        "news_mention_count",
        "telegram_doc_count",
        "blog_doc_count",
        "premium_doc_count",
        "image_map_doc_count",
        "images_ocr_doc_count",
        "event_tagged_doc_count",
        "event_order_count",
        "event_rights_issue_count",
        "event_lawsuit_count",
        "event_guidance_count",
        "macro_news_doc_count",
        "macro_risk_on_ratio",
        "macro_risk_off_ratio",
        "macro_risk_signal",
        "qualitative_signal",
        "dup_guard_axis_weight_upside",
        "dup_guard_axis_weight_downside",
        "dup_guard_axis_weight_bm",
        "dup_guard_axis_weight_persistence",
        "dup_guard_corr_threshold",
        "dup_guard_axis_cap",
        "dup_guard_pre_high_corr_pair_count",
        "dup_guard_post_high_corr_pair_count",
        "dup_guard_actions",
        "dup_guard_pre_pairs",
        "dup_guard_post_pairs",
        "stage4_numeric_weight",
        "stage3_qual_weight",
        "stage4_link_formula",
        "brain_backend",
    ]

    empty_diag = {
        "corr_threshold": DUP_AXIS_CORR_THRESHOLD,
        "axis_cap": DUP_AXIS_WEIGHT_CAP,
        "axis_weights": dict(DUP_AXIS_BASE_WEIGHTS),
        "pre_high_corr_pairs": [],
        "post_high_corr_pairs": [],
        "actions": [],
        "pre_high_corr_pair_count": 0,
        "post_high_corr_pair_count": 0,
    }

    if not rows:
        return pd.DataFrame(columns=cols), empty_diag

    df = pd.DataFrame(rows)

    def _agg_group(g: pd.DataFrame) -> pd.Series:
        w = g["source_reliability"].astype(float)
        doc_ids = g["record_id"].astype(str)

        source_families = set(str(x) for x in g["source_family"].tolist())
        source_diversity_ratio = len(source_families) / 8.0

        ns = g[g["source_family"].isin(["news_rss", "news_rss_macro"])]

        base = {
            "doc_count": int(doc_ids.nunique()),
            "mention_count": int(len(g)),
            "upside_score": _weighted_mean(g["upside_score_doc"], w),
            "downside_risk_score": _weighted_mean(g["downside_risk_score_doc"], w),
            "bm_sector_fit_score": _weighted_mean(g["bm_sector_fit_score_doc"], w),
            "persistence_score_doc_mean": _weighted_mean(g["persistence_score_doc"], w),
            "source_diversity_ratio": float(_clip(source_diversity_ratio, 0.0, 1.0)),
            "source_reliability_mean": float(w.mean()) if len(w) else 0.0,
            "dart_doc_count": int(g.loc[g["source_family"] == "dart", "record_id"].nunique()),
            "news_doc_count": int(ns["record_id"].nunique()) if not ns.empty else 0,
            "news_mention_count": int(len(ns)) if not ns.empty else 0,
            "telegram_doc_count": int(g.loc[g["source_family"] == "text_telegram", "record_id"].nunique()),
            "blog_doc_count": int(g.loc[g["source_family"] == "text_blog", "record_id"].nunique()),
            "premium_doc_count": int(g.loc[g["source_family"] == "text_premium", "record_id"].nunique()),
            "image_map_doc_count": int(g.loc[g["source_family"] == "text_image_map", "record_id"].nunique()),
            "images_ocr_doc_count": int(g.loc[g["source_family"] == "text_images_ocr", "record_id"].nunique()),
            "event_tagged_doc_count": int(g.loc[g["event_tagged"] == 1, "record_id"].nunique()),
            "event_order_count": int(g.loc[g["event_order"] == 1, "record_id"].nunique()),
            "event_rights_issue_count": int(g.loc[g["event_rights_issue"] == 1, "record_id"].nunique()),
            "event_lawsuit_count": int(g.loc[g["event_lawsuit"] == 1, "record_id"].nunique()),
            "event_guidance_count": int(g.loc[g["event_guidance"] == 1, "record_id"].nunique()),
        }

        return pd.Series(base)

    g = df.groupby(["date", "symbol"], as_index=False).apply(_agg_group, include_groups=False).reset_index(drop=True)

    if macro_docs:
        md = pd.DataFrame(macro_docs)
        mg = md.groupby("date", as_index=False).agg(
            macro_news_doc_count=("record_id", "nunique"),
            macro_risk_signal=("macro_score", "mean"),
            macro_risk_on_ratio=("macro_score", lambda s: float((s > 0).mean())),
            macro_risk_off_ratio=("macro_score", lambda s: float((s < 0).mean())),
        )
        g = g.merge(mg, on="date", how="left")
    else:
        g["macro_news_doc_count"] = 0
        g["macro_risk_signal"] = 0.0
        g["macro_risk_on_ratio"] = 0.0
        g["macro_risk_off_ratio"] = 0.0

    for c in ["macro_news_doc_count", "macro_risk_signal", "macro_risk_on_ratio", "macro_risk_off_ratio"]:
        g[c] = g[c].fillna(0)

    # 축 점수 보정(중복 아닌 보조 보정만)
    g["upside_score"] = (
        g["upside_score"]
        + 8.0 * g["macro_risk_on_ratio"]
        - 6.0 * g["macro_risk_off_ratio"]
    ).clip(0.0, 100.0)

    g["downside_risk_score"] = (
        g["downside_risk_score"]
        + 12.0 * g["macro_risk_off_ratio"]
        - 6.0 * g["macro_risk_on_ratio"]
    ).clip(0.0, 100.0)

    g["bm_sector_fit_score"] = (
        0.72 * g["bm_sector_fit_score"]
        + 28.0 * g["source_diversity_ratio"]
        + 6.0 * (g["dart_doc_count"] > 0).astype(float)
        + 4.0 * (g["premium_doc_count"] > 0).astype(float)
        - 8.0 * g["macro_risk_off_ratio"]
    ).clip(0.0, 100.0)

    g = g.sort_values(["symbol", "date"], ascending=[True, True]).reset_index(drop=True)
    g["doc_presence"] = (g["doc_count"] > 0).astype(float)
    g["presence_roll_20"] = g.groupby("symbol")["doc_presence"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    g["mention_roll_20"] = g.groupby("symbol")["mention_count"].transform(lambda s: s.rolling(20, min_periods=1).mean())

    g["persistence_score"] = (
        0.50 * g["persistence_score_doc_mean"]
        + 35.0 * g["presence_roll_20"]
        + 15.0 * (g["mention_roll_20"].clip(0, 10) / 10.0)
    ).clip(0.0, 100.0)

    g["risk_score"] = g["downside_risk_score"].clip(0.0, 100.0)
    g["net_edge_score"] = (g["upside_score"] - g["downside_risk_score"]).clip(-100.0, 100.0)

    # 4축 대표값 [-1,1]
    g["dup_axis_upside_rep"] = ((g["upside_score"] - 50.0) / 50.0).clip(-1.0, 1.0)
    g["dup_axis_downside_rep"] = ((g["downside_risk_score"] - 50.0) / 50.0).clip(-1.0, 1.0)
    g["dup_axis_bm_rep"] = ((g["bm_sector_fit_score"] - 50.0) / 50.0).clip(-1.0, 1.0)
    g["dup_axis_persistence_rep"] = ((g["persistence_score"] - 50.0) / 50.0).clip(-1.0, 1.0)

    axis_col_map = {
        "upside": "dup_axis_upside_rep",
        "downside": "dup_axis_downside_rep",
        "bm": "dup_axis_bm_rep",
        "persistence": "dup_axis_persistence_rep",
    }
    axis_cols = [axis_col_map[k] for k in ["upside", "downside", "bm", "persistence"]]
    pre_pairs, _ = _axis_corr_pairs(g, axis_cols, DUP_AXIS_CORR_THRESHOLD)

    axis_weights = dict(DUP_AXIS_BASE_WEIGHTS)
    actions: list[dict] = []
    dropped: set[str] = set()
    for pair in pre_pairs:
        a = pair["axis_a"].replace("dup_axis_", "").replace("_rep", "")
        b = pair["axis_b"].replace("dup_axis_", "").replace("_rep", "")
        if a not in axis_weights or b not in axis_weights:
            continue
        loser = a if DUP_AXIS_PRIORITY.get(a, 0) < DUP_AXIS_PRIORITY.get(b, 0) else b
        if loser in dropped:
            continue
        axis_weights[loser] = 0.0
        dropped.add(loser)
        actions.append({"action": "drop_axis", "axis": loser, "reason": pair})

    for k in list(axis_weights.keys()):
        axis_weights[k] = float(max(0.0, min(DUP_AXIS_WEIGHT_CAP, axis_weights[k])))

    if sum(axis_weights.values()) <= 1e-12:
        axis_weights = dict(DUP_AXIS_BASE_WEIGHTS)

    sum_w = float(sum(axis_weights.values()))
    if sum_w <= 1e-12:
        sum_w = 1.0

    # downside는 위험축이므로 음(-) 기여
    g["qualitative_signal"] = (
        axis_weights["upside"] * g["dup_axis_upside_rep"]
        - axis_weights["downside"] * g["dup_axis_downside_rep"]
        + axis_weights["bm"] * g["dup_axis_bm_rep"]
        + axis_weights["persistence"] * g["dup_axis_persistence_rep"]
    ) / sum_w
    g["qualitative_signal"] = g["qualitative_signal"].clip(-1.0, 1.0)

    post_cols = [axis_col_map[k] for k in ["upside", "downside", "bm", "persistence"] if axis_weights[k] > 0.0]
    post_pairs, _ = _axis_corr_pairs(g, post_cols, DUP_AXIS_CORR_THRESHOLD) if len(post_cols) >= 2 else ([], pd.DataFrame())

    g["dup_guard_axis_weight_upside"] = axis_weights["upside"]
    g["dup_guard_axis_weight_downside"] = axis_weights["downside"]
    g["dup_guard_axis_weight_bm"] = axis_weights["bm"]
    g["dup_guard_axis_weight_persistence"] = axis_weights["persistence"]
    g["dup_guard_corr_threshold"] = DUP_AXIS_CORR_THRESHOLD
    g["dup_guard_axis_cap"] = DUP_AXIS_WEIGHT_CAP
    g["dup_guard_pre_high_corr_pair_count"] = int(len(pre_pairs))
    g["dup_guard_post_high_corr_pair_count"] = int(len(post_pairs))
    g["dup_guard_actions"] = json.dumps(actions, ensure_ascii=False)
    g["dup_guard_pre_pairs"] = json.dumps(pre_pairs, ensure_ascii=False)
    g["dup_guard_post_pairs"] = json.dumps(post_pairs, ensure_ascii=False)

    g["stage4_numeric_weight"] = 0.80
    g["stage3_qual_weight"] = 0.20
    g["stage4_link_formula"] = "COMPOSITE = 0.80*VALUE_SCORE + 0.20*QUALITATIVE_SIGNAL"
    g["brain_backend"] = backend

    for c in cols:
        if c not in g.columns:
            g[c] = ""

    dup_diag = {
        "corr_threshold": DUP_AXIS_CORR_THRESHOLD,
        "axis_cap": DUP_AXIS_WEIGHT_CAP,
        "axis_weights": axis_weights,
        "pre_high_corr_pairs": pre_pairs,
        "post_high_corr_pairs": post_pairs,
        "actions": actions,
        "pre_high_corr_pair_count": int(len(pre_pairs)),
        "post_high_corr_pair_count": int(len(post_pairs)),
    }

    g = g[cols].sort_values(["date", "symbol"], ascending=[True, True]).reset_index(drop=True)
    return g, dup_diag


def _build_dart_signal(feat: pd.DataFrame) -> pd.DataFrame:
    if feat.empty:
        return pd.DataFrame(columns=[
            "date",
            "symbol",
            "dart_doc_count",
            "event_order_count",
            "event_rights_issue_count",
            "event_lawsuit_count",
            "event_guidance_count",
            "dart_event_signal",
        ])

    x = feat.copy()
    x = x[x["dart_doc_count"] > 0].copy()
    if x.empty:
        return pd.DataFrame(columns=[
            "date",
            "symbol",
            "dart_doc_count",
            "event_order_count",
            "event_rights_issue_count",
            "event_lawsuit_count",
            "event_guidance_count",
            "dart_event_signal",
        ])

    x["dart_event_signal"] = (
        x["event_order_count"]
        - x["event_rights_issue_count"]
        - x["event_lawsuit_count"]
        + 0.5 * x["event_guidance_count"]
    ) / x["doc_count"].clip(lower=1)
    x["dart_event_signal"] = x["dart_event_signal"].clip(-1.0, 1.0)

    return x[
        [
            "date",
            "symbol",
            "dart_doc_count",
            "event_order_count",
            "event_rights_issue_count",
            "event_lawsuit_count",
            "event_guidance_count",
            "dart_event_signal",
        ]
    ].sort_values(["date", "symbol"], ascending=[True, True]).reset_index(drop=True)


def _parse_args() -> Config:
    p = argparse.ArgumentParser(description="Stage3 local-brain qualitative 4-axis gate")
    p.add_argument("--input-jsonl", default=str(INPUT_DEFAULT))
    p.add_argument("--output-csv", default=str(OUTPUT_DEFAULT))
    p.add_argument("--dart-signal-csv", default=str(DART_SIGNAL_OUTPUT_DEFAULT))
    p.add_argument("--summary-json", default=str(SUMMARY_DEFAULT))
    p.add_argument("--backend", choices=["keyword_local", "llama_local"], default="keyword_local")
    p.add_argument("--local-endpoint", default="http://127.0.0.1:11434")
    p.add_argument("--local-model", default="llama_local_v1")
    p.add_argument("--bootstrap-empty-ok", action="store_true")
    a = p.parse_args()

    return Config(
        input_jsonl=Path(a.input_jsonl),
        output_csv=Path(a.output_csv),
        dart_signal_csv=Path(a.dart_signal_csv),
        summary_json=Path(a.summary_json),
        backend=a.backend,
        local_endpoint=a.local_endpoint,
        local_model=a.local_model,
        bootstrap_empty_ok=bool(a.bootstrap_empty_ok),
    )


def main() -> None:
    cfg = _parse_args()

    _assert_local_brain_guard(cfg.backend, cfg.local_endpoint, cfg.local_model)

    rows, macro_docs, errors, load_stats = _load_rows(cfg)
    if errors:
        _fail("; ".join(errors[:20]), 43)

    feat, dup_diag = _build_features(rows, macro_docs, cfg.backend)
    if feat.empty and not cfg.bootstrap_empty_ok:
        _fail("no_valid_records_after_validation", 44)

    cfg.output_csv.parent.mkdir(parents=True, exist_ok=True)
    cfg.summary_json.parent.mkdir(parents=True, exist_ok=True)
    cfg.dart_signal_csv.parent.mkdir(parents=True, exist_ok=True)

    feat.to_csv(cfg.output_csv, index=False)
    dart_sig = _build_dart_signal(feat)
    dart_sig.to_csv(cfg.dart_signal_csv, index=False)

    rows_df = pd.DataFrame(rows)
    summary = {
        "stage": "stage3_qualitative_axes_gate_local_brain",
        "local_brain_enforced": True,
        "backend": cfg.backend,
        "local_endpoint": cfg.local_endpoint,
        "input_jsonl": str(cfg.input_jsonl),
        "output_csv": str(cfg.output_csv),
        "dart_signal_csv": str(cfg.dart_signal_csv),
        "records_loaded": int(load_stats.get("docs_loaded", 0)),
        "records_scanned": int(load_stats.get("docs_scanned", 0)),
        "records_dedup_dropped": int(load_stats.get("docs_dedup_dropped", 0)),
        "records_macro_only": int(load_stats.get("docs_skipped_macro_only", 0)),
        "source_docs": load_stats.get("source_docs", {}),
        "mentions_loaded": int(len(rows)),
        "news_docs_loaded": int(rows_df.loc[rows_df["source_family"].isin(["news_rss", "news_rss_macro"]), "record_id"].nunique()) if not rows_df.empty else 0,
        "telegram_docs_loaded": int(rows_df.loc[rows_df["source_family"] == "text_telegram", "record_id"].nunique()) if not rows_df.empty else 0,
        "blog_docs_loaded": int(rows_df.loc[rows_df["source_family"] == "text_blog", "record_id"].nunique()) if not rows_df.empty else 0,
        "premium_docs_loaded": int(rows_df.loc[rows_df["source_family"] == "text_premium", "record_id"].nunique()) if not rows_df.empty else 0,
        "image_map_docs_loaded": int(rows_df.loc[rows_df["source_family"] == "text_image_map", "record_id"].nunique()) if not rows_df.empty else 0,
        "images_ocr_docs_loaded": int(rows_df.loc[rows_df["source_family"] == "text_images_ocr", "record_id"].nunique()) if not rows_df.empty else 0,
        "macro_news_docs_loaded": int(pd.DataFrame(macro_docs)["record_id"].nunique()) if macro_docs else 0,
        "symbols_output": int(feat["symbol"].nunique()) if not feat.empty else 0,
        "rows_output": int(len(feat)),
        "dart_signal_rows": int(len(dart_sig)),
        "axes": {
            "upside_score": "0~100 (higher is better)",
            "downside_risk_score": "0~100 (higher is riskier)",
            "risk_score": "0~100 (alias of downside_risk_score)",
            "bm_sector_fit_score": "0~100 (higher is better fit)",
            "persistence_score": "0~100 (higher is more persistent)",
        },
        "duplication_guard": {
            "rules_enabled": [
                "axis_representative_one",
                "cross_axis_corr_drop_if_abs_rho_gt_0_7",
                "single_axis_weight_cap_0_25",
            ],
            "corr_threshold": dup_diag.get("corr_threshold"),
            "axis_cap": dup_diag.get("axis_cap"),
            "axis_weights": dup_diag.get("axis_weights", {}),
            "pre_high_corr_pair_count": int(dup_diag.get("pre_high_corr_pair_count", 0)),
            "post_high_corr_pair_count": int(dup_diag.get("post_high_corr_pair_count", 0)),
            "actions": dup_diag.get("actions", []),
            "pre_high_corr_pairs": dup_diag.get("pre_high_corr_pairs", []),
            "post_high_corr_pairs": dup_diag.get("post_high_corr_pairs", []),
        },
        "bootstrap_empty_ok": cfg.bootstrap_empty_ok,
    }
    cfg.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = STAGE_ROOT / "outputs" / f"manifest_stage3_qual_axes_{ts}.json"
    write_run_manifest(
        run_type="stage3_qualitative_axes_local_brain",
        params={
            "backend": cfg.backend,
            "local_endpoint": cfg.local_endpoint,
            "local_model": cfg.local_model,
            "bootstrap_empty_ok": cfg.bootstrap_empty_ok,
        },
        inputs=[str(cfg.input_jsonl)],
        outputs=[str(cfg.output_csv), str(cfg.dart_signal_csv), str(cfg.summary_json)],
        out_path=str(manifest_path),
        workdir=str(WORKSPACE_ROOT),
    )

    print(f"STAGE3_DONE output={cfg.output_csv}")
    print(f"STAGE3_DART_SIGNAL={cfg.dart_signal_csv}")
    print(f"STAGE3_SUMMARY={cfg.summary_json}")
    print(f"STAGE3_MANIFEST={manifest_path}")


if __name__ == "__main__":
    main()
