#!/usr/bin/env python3
"""Fetch recent journal articles from OpenAlex and classify their abstracts."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNALS = json.loads((ROOT / "config" / "journals.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "data" / "papers.json"
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "365"))
PER_JOURNAL = int(os.getenv("PER_JOURNAL", "40"))
MAILTO = os.getenv("OPENALEX_MAILTO", "")

METHODS = {
    "Difference-in-Differences": [r"difference[- ]in[- ]differences?", r"difference[- ]in[- ]difference", r"\bdid\b"],
    "Event Study": [r"event[- ]study", r"event[- ]time"],
    "Instrumental Variables": [r"instrumental variables?", r"\b2sls\b", r"two[- ]stage least squares"],
    "Regression Discontinuity": [r"regression discontinuity", r"\brdd\b"],
    "Synthetic Control": [r"synthetic control"],
    "Randomized Experiment": [r"randomi[sz]ed (?:controlled )?(?:trial|experiment)", r"random assignment"],
    "Field Experiment": [r"field experiment"],
    "A/B Test": [r"\ba/b test", r"split test"],
    "Fixed Effects / Panel Data": [r"fixed[- ]effects?", r"panel data"],
    "Matching": [r"propensity score", r"coarsened exact matching", r"matching estimator"],
    "GMM / Dynamic Panel": [r"generalized method of moments", r"\bgmm\b", r"dynamic panel"],
    "Time-Series Analysis": [r"time[- ]series", r"vector autoregression", r"autoregressive"],
    "Survival / Hazard Model": [r"survival analys", r"hazard model", r"cox proportional"],
    "Discrete Choice Model": [r"discrete choice", r"multinomial logit", r"conditional logit"],
}

TOPICS = {
    "Generative AI": [r"generative ai", r"generative artificial intelligence", r"large language models?", r"\bllms?\b", r"foundation models?", r"chatgpt"],
    "Human–AI Interaction": [r"human[-– ]ai interaction", r"human[-– ]machine interaction", r"interact(?:ion|ing|s)? with (?:an? )?(?:ai|algorithm)", r"user interaction with (?:ai|algorithm)"],
    "Digital Platforms": [r"digital platforms?", r"online platforms?", r"platform[- ]mediated", r"multi[- ]sided platforms?"],
    "Platform Governance": [r"platform governance", r"platform polic(?:y|ies)", r"platform regulation", r"content moderation", r"platform rules?"],
    "Open Source Software": [r"open[- ]source software", r"open[- ]source communit", r"github repositor", r"software contributors?"],
    "Digital Labor": [r"digital labor", r"digital labour", r"gig workers?", r"gig econom", r"online labor", r"platform workers?", r"crowdwork"],
    "Digital Innovation": [r"digital innovation", r"digital transformation", r"digital technolog(?:y|ies).{0,45}innovation", r"innovation.{0,45}digital technolog"],
    "Entrepreneurship": [r"entrepreneur", r"new venture", r"startup"],
    "Information Economics": [r"information asymmetr", r"information disclosure", r"signaling"],
    "Human–AI Collaboration": [r"human[-– ]ai collaboration", r"human[-– ]ai teaming", r"human[-– ]machine collaboration", r"collaborat(?:e|ion|ing).{0,45}(?:ai|artificial intelligence)", r"(?:ai|artificial intelligence).{0,45}collaborat"],
    "AI Agent": [r"\bai agents?\b", r"artificial intelligence agents?", r"llm[- ]based agents?", r"agentic ai", r"autonomous (?:ai )?agents?"],
    "Decision Making": [r"decision[- ]making", r"decision support", r"managerial decisions?", r"consumer decisions?", r"judgment and choice"],
    "Information Ecosystems": [r"information ecosystems?", r"digital information environment", r"online information environment", r"information diffusion", r"information network"],
    "Platform Economy": [r"platform econom", r"two[- ]sided markets?", r"multi[- ]sided markets?", r"platform markets?"],
    "AI Agent Collaboration": [r"(?:ai|llm[- ]based|autonomous) agents?.{0,60}(?:collaborat|cooperat|coordinat)", r"multi[- ]agent collaboration", r"collaborative (?:ai )?agents?"],
    "AI Agent Information Systems": [r"(?:ai|llm[- ]based) agents?.{0,60}information systems?", r"agentic information systems?", r"information systems?.{0,60}(?:ai|autonomous) agents?"],
}

QUANTITATIVE_SIGNALS = [
    r"difference[- ]in[- ]differences?", r"event[- ]study", r"instrumental variables?", r"regression discontinuity",
    r"synthetic control", r"fixed[- ]effects?", r"panel data", r"randomi[sz]ed", r"field experiment", r"a/b test",
    r"regression", r"econometric", r"causal effect", r"treatment effect", r"natural experiment", r"quasi[- ]experiment",
    r"longitudinal data", r"administrative data", r"transaction data", r"observational data", r"large[- ]scale data",
    r"statistical analys", r"empirical analys", r"estimate(?:d|s|) the (?:effect|impact)", r"hazard model", r"time[- ]series",
    r"propensity score", r"matching estimator", r"generalized method of moments", r"discrete choice", r"logit model",
]

NON_QUANTITATIVE_ONLY = [r"ethnograph", r"qualitative stud", r"interview stud", r"case stud(?:y|ies)"]


def reconstruct_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    words = [(position, word) for word, positions in inverted_index.items() for position in positions]
    return " ".join(word for _, word in sorted(words))


def classify(text: str, dictionary: dict[str, list[str]]) -> list[str]:
    normalized = text.lower()
    return [label for label, patterns in dictionary.items() if any(re.search(pattern, normalized) for pattern in patterns)]


def is_quantitative(text: str, methods: list[str]) -> bool:
    normalized = text.lower()
    has_quant_signal = bool(methods) or any(re.search(pattern, normalized) for pattern in QUANTITATIVE_SIGNALS)
    qualitative_only = any(re.search(pattern, normalized) for pattern in NON_QUANTITATIVE_ONLY) and not has_quant_signal
    return has_quant_signal and not qualitative_only


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "PaperRadar/1.0 (academic literature monitor)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_journal(journal: dict, start_date: str, prior_first_seen: dict[str, str]) -> list[dict]:
    filters = f"primary_location.source.issn:{journal['issn']},from_publication_date:{start_date},type:article"
    params = {"filter": filters, "sort": "publication_date:desc", "per-page": str(PER_JOURNAL)}
    if MAILTO:
        params["mailto"] = MAILTO
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    results = fetch_json(url).get("results", [])
    papers = []
    for work in results:
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
        title = work.get("title") or "Untitled"
        combined = f"{title}. {abstract}"
        doi = work.get("doi") or ""
        work_id = work.get("id", "").rsplit("/", 1)[-1]
        stable_id = doi.removeprefix("https://doi.org/") or work_id
        methods = classify(combined, METHODS)
        topics = classify(combined, TOPICS)
        quantitative = is_quantitative(combined, methods)
        if not topics or not quantitative:
            continue
        if not methods:
            methods = ["Other Quantitative Empirical"]
        primary_location = work.get("primary_location") or {}
        papers.append({
            "id": work_id,
            "doi": doi.removeprefix("https://doi.org/"),
            "title": title,
            "authors": [item.get("author", {}).get("display_name", "") for item in work.get("authorships", []) if item.get("author")],
            "journal": journal["name"],
            "journal_short": journal["short"],
            "publication_date": work.get("publication_date"),
            "abstract": abstract,
            "first_seen_at": prior_first_seen.get(stable_id, date.today().isoformat()),
            "methods": methods,
            "topics": topics,
            "is_quantitative": True,
            "cited_by_count": work.get("cited_by_count", 0),
            "open_access": work.get("open_access", {}).get("is_oa", False),
            "doi_url": doi,
            "journal_url": primary_location.get("landing_page_url") or doi or work.get("id"),
            "url": doi or primary_location.get("landing_page_url") or work.get("id"),
        })
    return papers


def main() -> None:
    start_date = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    prior_first_seen: dict[str, str] = {}
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8")).get("papers", [])
            prior_first_seen = {(item.get("doi") or item.get("id")): item.get("first_seen_at") for item in previous if item.get("first_seen_at")}
        except (json.JSONDecodeError, OSError):
            pass
    all_papers: list[dict] = []
    errors: list[dict] = []
    for journal in JOURNALS:
        try:
            papers = fetch_journal(journal, start_date, prior_first_seen)
            all_papers.extend(papers)
            print(f"{journal['short']}: {len(papers)} papers")
        except Exception as exc:  # preserve other journals if one source temporarily fails
            errors.append({"journal": journal["name"], "error": str(exc)})
            print(f"{journal['short']}: ERROR {exc}")
        time.sleep(0.12)
    all_papers.sort(key=lambda item: item.get("publication_date") or "", reverse=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "paper_count": len(all_papers),
        "errors": errors,
        "papers": all_papers,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all_papers:
        raise SystemExit("No papers were fetched; refusing to publish an empty feed")


if __name__ == "__main__":
    main()
