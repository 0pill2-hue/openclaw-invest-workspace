#!/usr/bin/env python3
"""
Stage3 - Qualitative Axes Gate (LOCAL BRAIN ONLY)

목적
- Stage2 clean 기반 canonical intermediate corpus(`stage2_text_meta_records.jsonl`)를 읽어
  로컬모델 친화적인 짧은 chunk + focus_symbol 단위 claim-card를 만든다.
- Stage3의 실질 평가 단위를 `(record_id, chunk_id, focus_symbol)`로 고정한다.
- 최종 점수는 claim-card를 `(symbol, date, issue_cluster_id)`로 묶은 뒤 rule engine이 집계한다.
- 감성/주목도(attention/sentiment) 축은 운영점수에서 제거한다.
- remote/cloud 모델 사용을 금지하고, 로컬 정책 위반 시 FAIL-CLOSE 한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
CLAIM_CARD_OUTPUT_DEFAULT = STAGE_ROOT / "outputs/features/stage3_claim_cards.jsonl"
DART_SIGNAL_OUTPUT_DEFAULT = STAGE_ROOT / "outputs/signal/dart_event_signal.csv"
MACRO_FORECAST_OUTPUT_DEFAULT = STAGE_ROOT / "outputs/signal/stage3_macro_forecast.csv"
SUMMARY_DEFAULT = STAGE_ROOT / "outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json"

UPSIDE_WORDS = {
    "성장", "개선", "확대", "수주", "계약", "흑자", "상향", "반등", "증가", "회복",
    "신제품", "점유율", "가이던스", "성공", "강세",
    "growth", "improve", "expand", "order", "beat", "upgrade", "strong", "recovery",
    "guidance", "share gain", "launch",
}
DOWNSIDE_WORDS = {
    "감소", "부진", "하락", "적자", "둔화", "악화", "소송", "분쟁", "유상증자", "리스크",
    "규제", "지연", "차질", "정정", "우려",
    "decline", "weak", "drop", "loss", "lawsuit", "dispute", "dilution", "downgrade", "risk",
    "regulation", "delay", "concern",
}
PERSIST_POS_WORDS = {
    "지속", "장기", "반복", "연속", "누적", "중장기", "pipeline", "recurring", "long-term",
    "backlog", "구조적", "계속",
}
PERSIST_NEG_WORDS = {
    "일회성", "단기", "일시", "변동성", "불확실", "temporary", "one-off", "volatile", "uncertain",
    "반짝", "소멸",
}

EVENT_KEYWORDS = {
    "order": ["수주", "공급계약", "단일판매", "계약체결", "수주계약", "판매계약"],
    "rights_issue": ["유상증자", "증자", "전환사채", "cb", "bw", "신주발행", "희석"],
    "lawsuit": ["소송", "피소", "판결", "항소", "가처분", "분쟁"],
    "guidance": ["가이던스", "실적전망", "전망치", "컨센서스", "잠정실적", "실적발표"],
}

RISK_ON_WORDS = {
    "완화", "인하", "랠리", "상승", "회복", "risk-on", "risk on", "soft landing", "stimulus", "easing",
}
RISK_OFF_WORDS = {
    "긴축", "인상", "침체", "전쟁", "관세", "하락", "위기", "리스크오프", "risk-off", "risk off", "recession", "conflict", "sanction",
}

SOURCE_RELIABILITY = {
    "dart": 1.00,
    "news_rss": 0.94,
    "news_rss_macro": 0.94,
    "market_selected_articles": 0.91,
    "text_telegram": 0.68,
    "text_blog": 0.72,
    "text_premium": 0.84,
    "text_image_map": 0.58,
    "text_images_ocr": 0.55,
    "other": 0.55,
}

SOURCE_BM_BASE = {
    "dart": 0.92,
    "news_rss": 0.76,
    "news_rss_macro": 0.66,
    "market_selected_articles": 0.80,
    "text_premium": 0.82,
    "text_blog": 0.68,
    "text_telegram": 0.62,
    "text_image_map": 0.58,
    "text_images_ocr": 0.56,
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

CHUNK_POLICY = {
    "dart": {"target_chars": 220, "max_chunks": 1},
    "news_rss": {"target_chars": 420, "max_chunks": 2},
    "news_rss_macro": {"target_chars": 420, "max_chunks": 2},
    "market_selected_articles": {"target_chars": 650, "max_chunks": 4},
    "text_telegram": {"target_chars": 700, "max_chunks": 4},
    "text_blog": {"target_chars": 750, "max_chunks": 5},
    "text_premium": {"target_chars": 750, "max_chunks": 5},
    "text_image_map": {"target_chars": 550, "max_chunks": 3},
    "text_images_ocr": {"target_chars": 500, "max_chunks": 3},
    "other": {"target_chars": 650, "max_chunks": 4},
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "after", "before", "about", "market",
    "stock", "company", "기업", "시장", "투자", "기사", "뉴스", "증권", "대한", "관련", "에서", "으로", "하는",
}


@dataclass
class Config:
    input_jsonl: Path
    output_csv: Path
    claim_card_jsonl: Path
    dart_signal_csv: Path
    macro_forecast_csv: Path
    summary_json: Path
    backend: str
    local_endpoint: str
    local_model: str
    apply_macro_to_stock_axes: bool
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


def _canonical_source_family(source: str, explicit: str = "") -> str:
    s = (explicit or "").strip().lower()
    if s.endswith("_nosymbol"):
        s = s[: -len("_nosymbol")]
    if s in SOURCE_RELIABILITY:
        return s

    src = (source or "").strip().lower()
    if src == "dart" or src.startswith("dart"):
        return "dart"
    if src.startswith("rss_macro:"):
        return "news_rss_macro"
    if src.startswith("rss:"):
        return "news_rss"
    if src.startswith("market/selected_articles"):
        return "market_selected_articles"
    if src.startswith("text/telegram"):
        return "text_telegram"
    if src.startswith("text/blog"):
        return "text_blog"
    if src.startswith("text/premium"):
        return "text_premium"
    if src.startswith("text/image_map"):
        return "text_image_map"
    if src.startswith("text/images_ocr"):
        return "text_images_ocr"
    return "other"


def _normalize_symbols(symbols: object) -> tuple[list[str], list[str]]:
    if not isinstance(symbols, list):
        return [], []
    actual: list[str] = []
    placeholders: list[str] = []
    for raw in symbols:
        s = str(raw or "").strip().upper()
        if not s:
            continue
        if s.startswith("__") and s.endswith("__"):
            if s not in placeholders:
                placeholders.append(s)
            continue
        if s not in actual:
            actual.append(s)
    return actual, placeholders


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    out = [p.strip() for p in parts if p.strip()]
    return out or [text]


def _chunk_text(text: str, source_family: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    policy = CHUNK_POLICY.get(source_family, CHUNK_POLICY["other"])
    target_chars = int(policy["target_chars"])
    max_chunks = int(policy["max_chunks"])

    if source_family == "dart":
        return [text[:target_chars]]

    blocks = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = _split_sentences(text)

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for block in blocks:
        if not block:
            continue
        block_len = len(block)
        if buf and buf_len + block_len + 1 > target_chars:
            chunks.append("\n".join(buf).strip())
            buf = [block]
            buf_len = block_len
        else:
            buf.append(block)
            buf_len += block_len + (1 if buf else 0)
    if buf:
        chunks.append("\n".join(buf).strip())

    if not chunks:
        chunks = [text[:target_chars]]

    trimmed = [c[: max(target_chars + 120, target_chars)] for c in chunks if c.strip()]
    return trimmed[:max_chunks]


def _detect_event_flags(text: str, source_family: str) -> dict[str, bool]:
    flags = {k: False for k in EVENT_KEYWORDS.keys()}
    if source_family not in {"dart", "news_rss", "news_rss_macro", "market_selected_articles", "text_premium", "text_blog", "text_telegram"}:
        return flags

    tl = (text or "").lower()
    for ev, kws in EVENT_KEYWORDS.items():
        flags[ev] = any(kw.lower() in tl for kw in kws)

    if source_family == "dart":
        if "주주총회" in text or "지분" in text:
            flags["guidance"] = flags["guidance"] or False
    return flags


def _infer_macro_risk(text: str) -> tuple[float, int, int, bool]:
    tl = (text or "").lower()
    if not tl:
        return 0.0, 0, 0, False

    on = sum(1 for k in RISK_ON_WORDS if k in tl)
    off = sum(1 for k in RISK_OFF_WORDS if k in tl)
    if on + off == 0:
        return 0.0, 0, 0, False

    score = (on - off) / max(on + off, 1)
    return _clip(score, -1.0, 1.0), int(on), int(off), True


def _evidence_sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"\n+", text or ""):
        out.extend(_split_sentences(part))
    return [s.strip() for s in out if s.strip()]


def _extract_evidence_snippet(text: str, flags: dict[str, bool]) -> str:
    sentences = _evidence_sentences(text)
    strong_keywords = set(UPSIDE_WORDS) | set(DOWNSIDE_WORDS) | set(PERSIST_POS_WORDS) | set(PERSIST_NEG_WORDS)
    for ev, present in flags.items():
        if present:
            strong_keywords.update(EVENT_KEYWORDS.get(ev, []))

    for sent in sentences:
        low = sent.lower()
        if any(k.lower() in low for k in strong_keywords):
            return sent[:260]
    return (sentences[0] if sentences else text)[:260]


def _extract_macro_evidence_snippet(text: str) -> str:
    sentences = _evidence_sentences(text)
    keywords = {str(k).lower() for k in (set(RISK_ON_WORDS) | set(RISK_OFF_WORDS))}
    for sent in sentences:
        low = sent.lower()
        if any(k in low for k in keywords):
            return sent[:260]
    return (sentences[0] if sentences else text)[:260]


def _score_claim_card(text: str, source_family: str, flags: dict[str, bool]) -> dict[str, float | str]:
    toks = _tokenize(text)
    n_toks = len(toks)

    up_hits = sum(1 for t in toks if t in UPSIDE_WORDS)
    down_hits = sum(1 for t in toks if t in DOWNSIDE_WORDS)
    pers_pos = sum(1 for t in toks if t in PERSIST_POS_WORDS)
    pers_neg = sum(1 for t in toks if t in PERSIST_NEG_WORDS)
    event_hits = sum(int(v) for v in flags.values())
    has_number = bool(re.search(r"\d", text or ""))

    polarity = (up_hits - down_hits) / max(up_hits + down_hits, 1)
    pers_balance = (pers_pos - pers_neg) / max(pers_pos + pers_neg, 1)
    evidence_density = min(n_toks, 120) / 120.0

    upside = 50.0 + 22.0 * polarity + 8.0 * min(up_hits, 6) / 6.0
    downside = 50.0 - 20.0 * polarity + 10.0 * min(down_hits, 6) / 6.0
    bm_sector_fit = 100.0 * SOURCE_BM_BASE.get(source_family, SOURCE_BM_BASE["other"])
    persistence = 38.0 + 18.0 * pers_balance + 18.0 * evidence_density

    if flags.get("order", False):
        upside += 8.0
        persistence += 4.0
        bm_sector_fit += 4.0
    if flags.get("guidance", False):
        upside += 4.0
        persistence += 3.0
    if flags.get("rights_issue", False):
        downside += 12.0
        bm_sector_fit -= 5.0
        persistence -= 4.0
    if flags.get("lawsuit", False):
        downside += 10.0
        bm_sector_fit -= 6.0
        persistence -= 5.0

    if has_number:
        bm_sector_fit += 3.0
        persistence += 2.0

    if source_family == "dart":
        bm_sector_fit += 7.0
    elif source_family == "market_selected_articles":
        bm_sector_fit += 2.0

    upside = _clip(upside, 0.0, 100.0)
    downside = _clip(downside, 0.0, 100.0)
    bm_sector_fit = _clip(bm_sector_fit, 0.0, 100.0)
    persistence = _clip(persistence, 0.0, 100.0)

    axis_strength = {
        "upside": abs(upside - 50.0),
        "downside": abs(downside - 50.0),
        "bm": abs(bm_sector_fit - 50.0),
        "persistence": abs(persistence - 50.0),
    }
    dominant_axis = max(axis_strength.items(), key=lambda kv: kv[1])[0]

    confidence = _clip(
        0.32 + 0.08 * min(up_hits + down_hits + pers_pos + pers_neg, 5) + 0.10 * event_hits + (0.06 if has_number else 0.0),
        0.15,
        0.98,
    )
    claim_weight = _clip(
        SOURCE_RELIABILITY.get(source_family, SOURCE_RELIABILITY["other"]) * (0.85 + 0.18 * min(event_hits, 2) + 0.16 * min(evidence_density, 1.0) + 0.08 * (1.0 if has_number else 0.0)),
        0.20,
        2.00,
    )

    return {
        "upside_score_card": upside,
        "downside_risk_score_card": downside,
        "bm_sector_fit_score_card": bm_sector_fit,
        "persistence_score_card": persistence,
        "dominant_axis": dominant_axis,
        "claim_confidence": confidence,
        "claim_weight": claim_weight,
        "up_hits": float(up_hits),
        "down_hits": float(down_hits),
        "pers_pos_hits": float(pers_pos),
        "pers_neg_hits": float(pers_neg),
    }


def _issue_cluster_key(source_family: str, flags: dict[str, bool], text: str) -> str:
    events = [k for k, v in flags.items() if v]
    if events:
        return f"event:{'+'.join(sorted(events))}"

    toks = []
    for tok in _tokenize(text):
        if len(tok) < 2:
            continue
        if tok.isdigit():
            continue
        if tok in STOPWORDS:
            continue
        if tok not in toks:
            toks.append(tok)
        if len(toks) >= 3:
            break
    if toks:
        return f"topic:{source_family}:{'-'.join(toks)}"
    return f"topic:{source_family}:generic"


def _issue_cluster_id(date_kst: str, symbol: str, source_family: str, flags: dict[str, bool], text: str) -> str:
    key = _issue_cluster_key(source_family, flags, text)
    seed = f"{date_kst}:{symbol}:{key}"
    return hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _weighted_mean(v: pd.Series, w: pd.Series) -> float:
    ws = float(w.sum())
    if ws <= 0:
        return float(v.mean()) if len(v) else 0.0
    return float((v * w).sum() / ws)


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


def _new_load_stats() -> dict:
    return {
        "records_scanned": 0,
        "records_loaded": 0,
        "records_dedup_dropped": 0,
        "records_macro_only": 0,
        "records_skipped_nosymbol": 0,
        "claim_cards_generated": 0,
        "issue_clusters_generated": 0,
        "source_docs": {
            "dart": 0,
            "news_rss": 0,
            "news_rss_macro": 0,
            "market_selected_articles": 0,
            "text_telegram": 0,
            "text_blog": 0,
            "text_premium": 0,
            "text_image_map": 0,
            "text_images_ocr": 0,
            "other": 0,
        },
    }


def _load_claim_cards(cfg: Config) -> tuple[list[dict], list[dict], list[str], dict]:
    claim_cards: list[dict] = []
    macro_docs: list[dict] = []
    errors: list[str] = []
    stats = _new_load_stats()

    if not cfg.input_jsonl.exists():
        if cfg.bootstrap_empty_ok:
            return claim_cards, macro_docs, errors, stats
        errors.append(f"input_missing:{cfg.input_jsonl}")
        return claim_cards, macro_docs, errors, stats

    seen_fingerprint: set[str] = set()
    seen_clusters: set[str] = set()

    with cfg.input_jsonl.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            stats["records_scanned"] += 1

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
            explicit_source_family = str(obj.get("source_family", "")).strip()
            source_family = _canonical_source_family(source, explicit_source_family)

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
                stats["records_dedup_dropped"] += 1
                continue
            seen_fingerprint.add(fp)

            actual_symbols, placeholders = _normalize_symbols(symbols)
            chunks = _chunk_text(text, source_family)
            if not chunks:
                continue

            if not actual_symbols:
                if "__MACRO__" in placeholders or source_family == "news_rss_macro":
                    for chunk_idx, chunk_text in enumerate(chunks, start=1):
                        macro_score, macro_on, macro_off, macro_has_signal = _infer_macro_risk(chunk_text)
                        if not macro_has_signal:
                            continue
                        macro_docs.append(
                            {
                                "date": date_kst,
                                "record_id": record_id,
                                "chunk_id": chunk_idx,
                                "macro_score": macro_score,
                                "risk_on_cnt": macro_on,
                                "risk_off_cnt": macro_off,
                                "source": source,
                                "source_family": source_family,
                                "evidence_text": _extract_macro_evidence_snippet(chunk_text),
                            }
                        )
                    stats["records_macro_only"] += 1
                    stats["source_docs"][source_family] = stats["source_docs"].get(source_family, 0) + 1
                    stats["records_loaded"] += 1
                    continue

                stats["records_skipped_nosymbol"] += 1
                stats["source_docs"][source_family] = stats["source_docs"].get(source_family, 0) + 1
                stats["records_loaded"] += 1
                continue

            source_reliability = SOURCE_RELIABILITY.get(source_family, SOURCE_RELIABILITY["other"])
            for sym in actual_symbols:
                for chunk_idx, chunk_text in enumerate(chunks, start=1):
                    flags = _detect_event_flags(chunk_text, source_family)
                    score = _score_claim_card(chunk_text, source_family, flags)
                    issue_cluster_id = _issue_cluster_id(date_kst, sym, source_family, flags, chunk_text)
                    seen_clusters.add(f"{date_kst}:{sym}:{issue_cluster_id}")
                    evidence = _extract_evidence_snippet(chunk_text, flags)
                    claim_card_id = hashlib.sha1(f"{record_id}:{sym}:{chunk_idx}:{issue_cluster_id}".encode("utf-8", errors="ignore")).hexdigest()[:20]
                    claim_cards.append(
                        {
                            "date": date_kst,
                            "symbol": sym,
                            "record_id": record_id,
                            "chunk_id": chunk_idx,
                            "focus_symbol": sym,
                            "claim_card_id": claim_card_id,
                            "issue_cluster_id": issue_cluster_id,
                            "source": source,
                            "source_family": source_family,
                            "source_reliability": source_reliability,
                            "chunk_text": chunk_text,
                            "evidence_text": evidence,
                            "upside_score_card": score["upside_score_card"],
                            "downside_risk_score_card": score["downside_risk_score_card"],
                            "bm_sector_fit_score_card": score["bm_sector_fit_score_card"],
                            "persistence_score_card": score["persistence_score_card"],
                            "dominant_axis": score["dominant_axis"],
                            "claim_confidence": score["claim_confidence"],
                            "claim_weight": score["claim_weight"],
                            "event_order": int(flags["order"]),
                            "event_rights_issue": int(flags["rights_issue"]),
                            "event_lawsuit": int(flags["lawsuit"]),
                            "event_guidance": int(flags["guidance"]),
                            "event_tagged": int(any(flags.values())),
                        }
                    )
                    stats["claim_cards_generated"] += 1

            stats["source_docs"][source_family] = stats["source_docs"].get(source_family, 0) + 1
            stats["records_loaded"] += 1

    stats["issue_clusters_generated"] = int(len(seen_clusters))
    return claim_cards, macro_docs, errors, stats


def _build_issue_clusters(claim_cards: list[dict]) -> pd.DataFrame:
    if not claim_cards:
        return pd.DataFrame(columns=[
            "date",
            "symbol",
            "issue_cluster_id",
            "cluster_weight",
            "cluster_claim_count",
            "cluster_doc_count",
            "cluster_upside_score",
            "cluster_downside_risk_score",
            "cluster_bm_sector_fit_score",
            "cluster_persistence_score",
        ])

    df = pd.DataFrame(claim_cards)

    def _agg_cluster(g: pd.DataFrame) -> pd.Series:
        w = g["claim_weight"].astype(float)
        return pd.Series(
            {
                "cluster_weight": float(max(w.sum(), 1.0)),
                "cluster_claim_count": int(len(g)),
                "cluster_doc_count": int(g["record_id"].nunique()),
                "cluster_upside_score": _weighted_mean(g["upside_score_card"], w),
                "cluster_downside_risk_score": _weighted_mean(g["downside_risk_score_card"], w),
                "cluster_bm_sector_fit_score": _weighted_mean(g["bm_sector_fit_score_card"], w),
                "cluster_persistence_score": _weighted_mean(g["persistence_score_card"], w),
            }
        )

    out = df.groupby(["date", "symbol", "issue_cluster_id"]).apply(_agg_cluster, include_groups=False).reset_index()
    return out.sort_values(["date", "symbol", "issue_cluster_id"]).reset_index(drop=True)


def _macro_regime_label(signal: float, risk_on_ratio: float, risk_off_ratio: float) -> str:
    if risk_on_ratio >= 0.60 and signal > 0.10:
        return "risk_on"
    if risk_off_ratio >= 0.60 and signal < -0.10:
        return "risk_off"
    if abs(signal) < 0.15 and abs(risk_on_ratio - risk_off_ratio) < 0.20:
        return "neutral"
    return "mixed"


def _macro_source_mix(values: list[str]) -> str:
    cleaned = [str(v or "").strip() or "other" for v in values]
    if not cleaned:
        return ""
    total = len(cleaned)
    counts = pd.Series(cleaned).value_counts()
    return ", ".join(f"{idx}:{count/total:.2f}" for idx, count in counts.items())


def _macro_evidence_summary(values: list[str], limit: int = 3) -> str:
    seen: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.append(text[:260])
        if len(seen) >= limit:
            break
    return " | ".join(seen)


def _build_macro_forecast(macro_docs: list[dict], backend: str) -> pd.DataFrame:
    cols = [
        "date",
        "macro_doc_count",
        "macro_risk_signal",
        "macro_risk_on_ratio",
        "macro_risk_off_ratio",
        "macro_regime_label",
        "macro_forecast_score",
        "macro_confidence",
        "macro_horizon",
        "macro_evidence_summary",
        "macro_source_mix",
        "brain_backend",
    ]
    if not macro_docs:
        return pd.DataFrame(columns=cols)

    md = pd.DataFrame(macro_docs)
    rows: list[dict] = []
    for date, group in md.groupby("date", sort=True):
        macro_doc_count = int(group["record_id"].nunique())
        macro_risk_signal = float(group["macro_score"].mean()) if len(group) else 0.0
        macro_risk_on_ratio = float((group["macro_score"] > 0).mean()) if len(group) else 0.0
        macro_risk_off_ratio = float((group["macro_score"] < 0).mean()) if len(group) else 0.0
        macro_regime_label = _macro_regime_label(macro_risk_signal, macro_risk_on_ratio, macro_risk_off_ratio)
        macro_forecast_score = _clip(50.0 + 35.0 * macro_risk_signal + 10.0 * (macro_risk_on_ratio - macro_risk_off_ratio), 0.0, 100.0)
        source_mix = _macro_source_mix(group["source_family"].astype(str).tolist())
        source_diversity = max(int(group["source_family"].astype(str).nunique()), 1)
        macro_confidence = _clip(
            0.35
            + 0.12 * min(macro_doc_count, 4) / 4.0
            + 0.20 * max(abs(macro_risk_signal), abs(macro_risk_on_ratio - macro_risk_off_ratio))
            + 0.08 * min(source_diversity, 3) / 3.0,
            0.20,
            0.97,
        )
        rows.append(
            {
                "date": date,
                "macro_doc_count": macro_doc_count,
                "macro_risk_signal": macro_risk_signal,
                "macro_risk_on_ratio": macro_risk_on_ratio,
                "macro_risk_off_ratio": macro_risk_off_ratio,
                "macro_regime_label": macro_regime_label,
                "macro_forecast_score": macro_forecast_score,
                "macro_confidence": macro_confidence,
                "macro_horizon": "1-5d",
                "macro_evidence_summary": _macro_evidence_summary(group["evidence_text"].astype(str).tolist()),
                "macro_source_mix": source_mix,
                "brain_backend": backend,
            }
        )

    return pd.DataFrame(rows, columns=cols).sort_values(["date"]).reset_index(drop=True)


def _build_features(claim_cards: list[dict], macro_docs: list[dict], backend: str, apply_macro_to_stock_axes: bool) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    cols = [
        "date",
        "symbol",
        "doc_count",
        "mention_count",
        "claim_card_count",
        "issue_cluster_count",
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
        "rss_doc_count",
        "selected_articles_doc_count",
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
        "macro_to_stock_axes_applied",
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

    macro_forecast = _build_macro_forecast(macro_docs, backend)

    if not claim_cards:
        return pd.DataFrame(columns=cols), empty_diag, macro_forecast

    cards = pd.DataFrame(claim_cards)
    clusters = _build_issue_clusters(claim_cards)

    def _agg_counts(g: pd.DataFrame) -> pd.Series:
        source_families = set(str(x) for x in g["source_family"].tolist())
        news_mask = g["source_family"].isin(["news_rss", "market_selected_articles"])
        return pd.Series(
            {
                "doc_count": int(g["record_id"].nunique()),
                "mention_count": int(len(g)),
                "claim_card_count": int(g["claim_card_id"].nunique()),
                "issue_cluster_count": int(g["issue_cluster_id"].nunique()),
                "source_diversity_ratio": float(_clip(len(source_families) / 7.0, 0.0, 1.0)),
                "source_reliability_mean": float(g["source_reliability"].astype(float).mean()) if len(g) else 0.0,
                "dart_doc_count": int(g.loc[g["source_family"] == "dart", "record_id"].nunique()),
                "news_doc_count": int(g.loc[news_mask, "record_id"].nunique()),
                "rss_doc_count": int(g.loc[g["source_family"] == "news_rss", "record_id"].nunique()),
                "selected_articles_doc_count": int(g.loc[g["source_family"] == "market_selected_articles", "record_id"].nunique()),
                "news_mention_count": int(news_mask.sum()),
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
        )

    count_df = cards.groupby(["date", "symbol"]).apply(_agg_counts, include_groups=False).reset_index()

    def _agg_scores(g: pd.DataFrame) -> pd.Series:
        w = g["cluster_weight"].astype(float)
        return pd.Series(
            {
                "upside_score": _weighted_mean(g["cluster_upside_score"], w),
                "downside_risk_score": _weighted_mean(g["cluster_downside_risk_score"], w),
                "bm_sector_fit_score": _weighted_mean(g["cluster_bm_sector_fit_score"], w),
                "persistence_score_cluster_mean": _weighted_mean(g["cluster_persistence_score"], w),
            }
        )

    score_df = clusters.groupby(["date", "symbol"]).apply(_agg_scores, include_groups=False).reset_index()
    g = count_df.merge(score_df, on=["date", "symbol"], how="left")

    if not macro_forecast.empty:
        macro_merge = macro_forecast.rename(columns={"macro_doc_count": "macro_news_doc_count"})[[
            "date",
            "macro_news_doc_count",
            "macro_risk_signal",
            "macro_risk_on_ratio",
            "macro_risk_off_ratio",
        ]]
        g = g.merge(macro_merge, on="date", how="left")
    else:
        g["macro_news_doc_count"] = 0
        g["macro_risk_signal"] = 0.0
        g["macro_risk_on_ratio"] = 0.0
        g["macro_risk_off_ratio"] = 0.0

    for c in ["macro_news_doc_count", "macro_risk_signal", "macro_risk_on_ratio", "macro_risk_off_ratio"]:
        g[c] = g[c].fillna(0)

    if apply_macro_to_stock_axes:
        g["upside_score"] = (
            g["upside_score"] + 7.0 * g["macro_risk_on_ratio"] - 6.0 * g["macro_risk_off_ratio"]
        ).clip(0.0, 100.0)
        g["downside_risk_score"] = (
            g["downside_risk_score"] + 11.0 * g["macro_risk_off_ratio"] - 5.0 * g["macro_risk_on_ratio"]
        ).clip(0.0, 100.0)
        g["bm_sector_fit_score"] = (
            0.74 * g["bm_sector_fit_score"]
            + 22.0 * g["source_diversity_ratio"]
            + 6.0 * (g["dart_doc_count"] > 0).astype(float)
            + 3.0 * (g["premium_doc_count"] > 0).astype(float)
            + 3.0 * (g["selected_articles_doc_count"] > 0).astype(float)
            - 7.0 * g["macro_risk_off_ratio"]
        ).clip(0.0, 100.0)

    g["macro_to_stock_axes_applied"] = "on" if apply_macro_to_stock_axes else "off"

    g = g.sort_values(["symbol", "date"], ascending=[True, True]).reset_index(drop=True)
    g["doc_presence"] = (g["doc_count"] > 0).astype(float)
    g["presence_roll_20"] = g.groupby("symbol")["doc_presence"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    g["cluster_roll_20"] = g.groupby("symbol")["issue_cluster_count"].transform(lambda s: s.rolling(20, min_periods=1).mean())

    g["persistence_score"] = (
        0.55 * g["persistence_score_cluster_mean"]
        + 25.0 * g["presence_roll_20"]
        + 20.0 * (g["cluster_roll_20"].clip(0, 6) / 6.0)
    ).clip(0.0, 100.0)

    g["risk_score"] = g["downside_risk_score"].clip(0.0, 100.0)
    g["net_edge_score"] = (g["upside_score"] - g["downside_risk_score"]).clip(-100.0, 100.0)

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

    sum_w = float(sum(axis_weights.values())) or 1.0
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
    return g, dup_diag, macro_forecast


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


def _write_claim_cards_jsonl(path: Path, claim_cards: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in claim_cards:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_args() -> Config:
    p = argparse.ArgumentParser(description="Stage3 local-brain qualitative 4-axis gate")
    p.add_argument("--input-jsonl", default=str(INPUT_DEFAULT))
    p.add_argument("--output-csv", default=str(OUTPUT_DEFAULT))
    p.add_argument("--claim-card-jsonl", default=str(CLAIM_CARD_OUTPUT_DEFAULT))
    p.add_argument("--dart-signal-csv", default=str(DART_SIGNAL_OUTPUT_DEFAULT))
    p.add_argument("--macro-forecast-csv", default=str(MACRO_FORECAST_OUTPUT_DEFAULT))
    p.add_argument("--summary-json", default=str(SUMMARY_DEFAULT))
    p.add_argument("--backend", choices=["keyword_local", "llama_local"], default="keyword_local")
    p.add_argument("--local-endpoint", default="http://127.0.0.1:11434")
    p.add_argument("--local-model", default="llama_local_v1")
    p.add_argument("--apply-macro-to-stock-axes", choices=["on", "off"], default="on")
    p.add_argument("--bootstrap-empty-ok", action="store_true")
    a = p.parse_args()

    return Config(
        input_jsonl=Path(a.input_jsonl),
        output_csv=Path(a.output_csv),
        claim_card_jsonl=Path(a.claim_card_jsonl),
        dart_signal_csv=Path(a.dart_signal_csv),
        macro_forecast_csv=Path(a.macro_forecast_csv),
        summary_json=Path(a.summary_json),
        backend=a.backend,
        local_endpoint=a.local_endpoint,
        local_model=a.local_model,
        apply_macro_to_stock_axes=(a.apply_macro_to_stock_axes == "on"),
        bootstrap_empty_ok=bool(a.bootstrap_empty_ok),
    )


def main() -> None:
    cfg = _parse_args()

    _assert_local_brain_guard(cfg.backend, cfg.local_endpoint, cfg.local_model)

    claim_cards, macro_docs, errors, load_stats = _load_claim_cards(cfg)
    if errors:
        _fail("; ".join(errors[:20]), 43)

    feat, dup_diag, macro_forecast = _build_features(claim_cards, macro_docs, cfg.backend, cfg.apply_macro_to_stock_axes)
    if feat.empty and not cfg.bootstrap_empty_ok:
        _fail("no_valid_records_after_validation", 44)

    cfg.output_csv.parent.mkdir(parents=True, exist_ok=True)
    cfg.summary_json.parent.mkdir(parents=True, exist_ok=True)
    cfg.dart_signal_csv.parent.mkdir(parents=True, exist_ok=True)
    cfg.macro_forecast_csv.parent.mkdir(parents=True, exist_ok=True)

    feat.to_csv(cfg.output_csv, index=False)
    _write_claim_cards_jsonl(cfg.claim_card_jsonl, claim_cards)

    dart_sig = _build_dart_signal(feat)
    dart_sig.to_csv(cfg.dart_signal_csv, index=False)

    macro_forecast.to_csv(cfg.macro_forecast_csv, index=False)

    cards_df = pd.DataFrame(claim_cards)
    summary = {
        "stage": "stage3_qualitative_axes_gate_local_brain",
        "local_brain_enforced": True,
        "backend": cfg.backend,
        "local_endpoint": cfg.local_endpoint,
        "input_jsonl": str(cfg.input_jsonl),
        "claim_card_jsonl": str(cfg.claim_card_jsonl),
        "output_csv": str(cfg.output_csv),
        "dart_signal_csv": str(cfg.dart_signal_csv),
        "macro_forecast_csv": str(cfg.macro_forecast_csv),
        "canonical_intermediate_corpus": str(cfg.input_jsonl),
        "units": {
            "storage_unit": "stage2_text_meta_records.jsonl row",
            "model_evaluation_unit": "(record_id, chunk_id, focus_symbol)",
            "aggregation_unit": "(symbol, date, issue_cluster_id) -> (symbol, date)",
        },
        "records_loaded": int(load_stats.get("records_loaded", 0)),
        "records_scanned": int(load_stats.get("records_scanned", 0)),
        "records_dedup_dropped": int(load_stats.get("records_dedup_dropped", 0)),
        "records_macro_only": int(load_stats.get("records_macro_only", 0)),
        "records_skipped_nosymbol": int(load_stats.get("records_skipped_nosymbol", 0)),
        "source_docs": load_stats.get("source_docs", {}),
        "claim_cards_generated": int(load_stats.get("claim_cards_generated", 0)),
        "issue_clusters_generated": int(load_stats.get("issue_clusters_generated", 0)),
        "mentions_loaded": int(len(claim_cards)),
        "news_docs_loaded": int(cards_df.loc[cards_df["source_family"].isin(["news_rss", "market_selected_articles"]), "record_id"].nunique()) if not cards_df.empty else 0,
        "rss_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "news_rss", "record_id"].nunique()) if not cards_df.empty else 0,
        "selected_articles_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "market_selected_articles", "record_id"].nunique()) if not cards_df.empty else 0,
        "telegram_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "text_telegram", "record_id"].nunique()) if not cards_df.empty else 0,
        "blog_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "text_blog", "record_id"].nunique()) if not cards_df.empty else 0,
        "premium_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "text_premium", "record_id"].nunique()) if not cards_df.empty else 0,
        "image_map_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "text_image_map", "record_id"].nunique()) if not cards_df.empty else 0,
        "images_ocr_docs_loaded": int(cards_df.loc[cards_df["source_family"] == "text_images_ocr", "record_id"].nunique()) if not cards_df.empty else 0,
        "macro_news_docs_loaded": int(pd.DataFrame(macro_docs)["record_id"].nunique()) if macro_docs else 0,
        "symbols_output": int(feat["symbol"].nunique()) if not feat.empty else 0,
        "rows_output": int(len(feat)),
        "dart_signal_rows": int(len(dart_sig)),
        "macro_forecast_rows": int(len(macro_forecast)),
        "apply_macro_to_stock_axes": cfg.apply_macro_to_stock_axes,
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
            "apply_macro_to_stock_axes": cfg.apply_macro_to_stock_axes,
        },
        inputs=[str(cfg.input_jsonl)],
        outputs=[str(cfg.output_csv), str(cfg.claim_card_jsonl), str(cfg.dart_signal_csv), str(cfg.macro_forecast_csv), str(cfg.summary_json)],
        out_path=str(manifest_path),
        workdir=str(WORKSPACE_ROOT),
    )

    print(f"STAGE3_DONE output={cfg.output_csv}")
    print(f"STAGE3_CLAIM_CARDS={cfg.claim_card_jsonl}")
    print(f"STAGE3_DART_SIGNAL={cfg.dart_signal_csv}")
    print(f"STAGE3_MACRO_FORECAST={cfg.macro_forecast_csv}")
    print(f"STAGE3_SUMMARY={cfg.summary_json}")
    print(f"STAGE3_MANIFEST={manifest_path}")


if __name__ == "__main__":
    main()
