#!/usr/bin/env python3
"""Fetch recent journal articles from OpenAlex and preserve accumulated papers."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
JOURNALS = json.loads(
    (ROOT / "config" / "journals.json").read_text(encoding="utf-8")
)
OUTPUT = ROOT / "data" / "papers.json"

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "365"))

# OpenAlex는 한 페이지당 최대 200개까지 반환할 수 있다.
PAGE_SIZE = min(
    max(int(os.getenv("OPENALEX_PAGE_SIZE", "200")), 1),
    200,
)

# 저널별 최대 10페이지, 즉 최대 2,000개의 최근 논문을 확인한다.
MAX_PAGES_PER_JOURNAL = max(
    int(os.getenv("MAX_PAGES_PER_JOURNAL", "10")),
    1,
)

ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "")

ELSEVIER_ISSNS = {
    "0378-7206",  # Information & Management
    "0167-9236",  # Decision Support Systems
}

MAILTO = os.getenv("OPENALEX_MAILTO", "")
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")

KST = ZoneInfo("Asia/Seoul")


METHODS = {
    "Difference-in-Differences": [
        r"difference[- ]in[- ]differences?",
        r"difference[- ]in[- ]difference",
        r"\bdid\b",
        r"staggered[- ]did",
        r"staggered difference[- ]in[- ]differences?",
        r"staggered adoption",
        r"triple difference",
        r"difference[- ]in[- ]difference[- ]in[- ]differences?",
        r"\bddd\b",
    ],

    "Event Study": [
        r"event[- ]study",
        r"event[- ]time",
        r"dynamic treatment effects?",
    ],

    "Natural / Quasi Experiment": [
        r"natural[- ]experiment",
        r"natural experimental",
        r"quasi[- ]experiment",
        r"quasi[- ]experimental",
        r"quasi experimental design",
    ],

    "Instrumental Variables": [
        r"instrumental variables?",
        r"instrumental variable approach",
        r"\biv estimation",
        r"\b2sls\b",
        r"two[- ]stage least squares",
    ],

    "Regression Discontinuity": [
        r"regression discontinuity",
        r"regression discontinuity design",
        r"\brdd\b",
        r"sharp rdd",
        r"fuzzy rdd",
    ],

    "Synthetic Control": [
        r"synthetic control",
        r"synthetic control method",
        r"synthetic difference[- ]in[- ]differences?",
    ],

    "Randomized Experiment": [
        r"randomi[sz]ed (?:controlled )?(?:trial|experiment)",
        r"random assignment",
        r"randomi[sz]ed intervention",
    ],

    "Field Experiment": [
        r"field experiment",
        r"field experimental",
    ],

    "A/B Test": [
        r"\ba/b test",
        r"split test",
        r"online experiment",
    ],

    "Fixed Effects / Panel Econometrics": [
        r"fixed[- ]effects?",
        r"two[- ]way fixed effects?",
        r"\btwfe\b",
        r"panel data",
        r"panel regression",
        r"panel econometric",
        r"longitudinal data",
    ],

    "Matching": [
        r"propensity score",
        r"propensity score matching",
        r"coarsened exact matching",
        r"matching estimator",
        r"nearest[- ]neighbor matching",
    ],

    "GMM / Dynamic Panel": [
        r"generalized method of moments",
        r"\bgmm\b",
        r"dynamic panel",
        r"system gmm",
        r"difference gmm",
        r"arellano[- ]bond",
    ],

    "Time-Series Analysis": [
        r"time[- ]series",
        r"vector autoregression",
        r"\bvar model",
        r"autoregressive",
        r"cointegration",
        r"error correction model",
        r"interrupted time[- ]series",
    ],

    "Survival / Hazard Model": [
        r"survival analys",
        r"hazard model",
        r"hazard regression",
        r"cox proportional",
        r"duration model",
    ],

    "Discrete Choice Model": [
        r"discrete choice",
        r"multinomial logit",
        r"conditional logit",
        r"mixed logit",
        r"random utility model",
    ],
        "Causal Inference": [
        r"causal inference",
        r"causal effect",
        r"causal impact",
        r"causal identification",
        r"identification strategy",
    ],

    "Econometric Analysis": [
        r"econometric analys",
        r"econometric model",
        r"econometric estimation",
        r"empirical econometric",
    ],

    "Selection / Endogeneity": [
        r"heckman selection",
        r"heckman correction",
        r"control function approach",
        r"endogeneity correction",
    ],

}


TOPICS = {
    "Generative AI": [
        r"generative ai",
        r"generative artificial intelligence",
        r"large language models?",
        r"\bllms?\b",
        r"foundation models?",
        r"chatgpt",
    ],
    "Human–AI Interaction": [
        r"human[-– ]ai interaction",
        r"human[-– ]machine interaction",
        r"interact(?:ion|ing|s)? with (?:an? )?(?:ai|algorithm)",
        r"user interaction with (?:ai|algorithm)",
    ],
    "Digital Platforms": [
        r"digital platforms?",
        r"online platforms?",
        r"platform[- ]mediated",
        r"multi[- ]sided platforms?",
    ],
    "Platform Governance": [
        r"platform governance",
        r"platform polic(?:y|ies)",
        r"platform regulation",
        r"content moderation",
        r"platform rules?",
    ],
    "Open Source Software": [
        r"open[- ]source software",
        r"open[- ]source communit",
        r"github repositor",
        r"software contributors?",
    ],
    "Digital Labor": [
        r"digital labor",
        r"digital labour",
        r"gig workers?",
        r"gig econom",
        r"online labor",
        r"platform workers?",
        r"crowdwork",
    ],
    "Digital Innovation": [
        r"digital innovation",
        r"digital transformation",
        r"digital technolog(?:y|ies).{0,45}innovation",
        r"innovation.{0,45}digital technolog",
    ],
    "Entrepreneurship": [
        r"entrepreneur",
        r"new venture",
        r"startup",
    ],
    "Information Economics": [
        r"information asymmetr",
        r"information disclosure",
        r"signaling",
    ],
    "Human–AI Collaboration": [
        r"human[-– ]ai collaboration",
        r"human[-– ]ai teaming",
        r"human[-– ]machine collaboration",
        r"collaborat(?:e|ion|ing).{0,45}(?:ai|artificial intelligence)",
        r"(?:ai|artificial intelligence).{0,45}collaborat",
    ],
    "AI Agent": [
        r"\bai agents?\b",
        r"artificial intelligence agents?",
        r"llm[- ]based agents?",
        r"agentic ai",
        r"autonomous (?:ai )?agents?",
    ],
    "Decision Making": [
        r"decision[- ]making",
        r"decision support",
        r"managerial decisions?",
        r"consumer decisions?",
        r"judgment and choice",
    ],
    "Information Ecosystems": [
        r"information ecosystems?",
        r"digital information environment",
        r"online information environment",
        r"information diffusion",
        r"information network",
    ],
    "Platform Economy": [
        r"platform econom",
        r"two[- ]sided markets?",
        r"multi[- ]sided markets?",
        r"platform markets?",
    ],
    "AI Agent Collaboration": [
        r"(?:ai|llm[- ]based|autonomous) agents?.{0,60}(?:collaborat|cooperat|coordinat)",
        r"multi[- ]agent collaboration",
        r"collaborative (?:ai )?agents?",
    ],
    "AI Agent Information Systems": [
        r"(?:ai|llm[- ]based) agents?.{0,60}information systems?",
        r"agentic information systems?",
        r"information systems?.{0,60}(?:ai|autonomous) agents?",
    ],
    "Crowdsourcing": [
        r"crowdsourcing",
        r"crowdsourcing contests?",
        r"crowd[- ]based",
        r"crowdwork",
        r"crowd workers?",
    ],

    "Online Communities": [
        r"online communit",
        r"virtual communit",
        r"online knowledge communit",
        r"online innovation communit",
        r"question[- ]and[- ]answer communit",
        r"\bq&a communit",
        r"knowledge[- ]sharing communit",
    ],

    "Social Networks": [
        r"social networks?",
        r"online social networks?",
        r"social networking",
        r"social media",
        r"network centrality",
        r"social ties?",
    ],

    "Open Source Software": [
        r"open[- ]source software",
        r"open source software",
        r"open[- ]source communit",
        r"open source communit",
        r"open[- ]source development",
        r"\boss\b",
        r"\boss projects?",
        r"github",
        r"software developers?",
        r"software contributors?",
    ],

    "Digital Healthcare": [
        r"digital health",
        r"digital healthcare",
        r"online health",
        r"online healthcare",
        r"online health communit",
        r"\bohc\b",
        r"telemedicine",
        r"telehealth",
        r"mobile health",
        r"\bmhealth\b",
        r"electronic health records?",
        r"\behr\b",
    ],

    "Online Platforms": [
        r"online platforms?",
        r"digital platforms?",
        r"platform[- ]based",
        r"platform[- ]mediated",
        r"platform users?",
        r"platform participants?",
    ],

    "Online Markets / E-Commerce": [
        r"online market",
        r"online marketplace",
        r"digital marketplace",
        r"e[- ]commerce",
        r"electronic commerce",
        r"online sellers?",
        r"online retailers?",
    ],

    "Crowdfunding": [
        r"crowdfunding",
        r"equity crowdfunding",
        r"charitable crowdfunding",
        r"online crowdfunding",
    ],

    "Sharing / Gig Economy": [
        r"sharing econom",
        r"gig econom",
        r"gig workers?",
        r"platform workers?",
        r"home[- ]sharing",
        r"ride[- ]sharing",
        r"ride[- ]hailing",
    ],

    "Online Knowledge Sharing": [
        r"knowledge sharing",
        r"knowledge contribution",
        r"knowledge co[- ]production",
        r"knowledge collaboration",
        r"knowledge[- ]sharing platform",
        r"online knowledge",
    ],
    
}


QUANTITATIVE_SIGNALS = [
    r"difference[- ]in[- ]differences?",
    r"event[- ]study",
    r"instrumental variables?",
    r"regression discontinuity",
    r"synthetic control",
    r"fixed[- ]effects?",
    r"panel data",
    r"randomi[sz]ed",
    r"field experiment",
    r"a/b test",
    r"regression",
    r"econometric",
    r"causal effect",
    r"treatment effect",
    r"natural experiment",
    r"quasi[- ]experiment",
    r"longitudinal data",
    r"administrative data",
    r"transaction data",
    r"observational data",
    r"large[- ]scale data",
    r"statistical analys",
    r"empirical analys",
    r"estimate(?:d|s|) the (?:effect|impact)",
    r"hazard model",
    r"time[- ]series",
    r"propensity score",
    r"matching estimator",
    r"generalized method of moments",
    r"discrete choice",
    r"logit model",
]


NON_QUANTITATIVE_ONLY = [
    r"ethnograph",
    r"qualitative stud",
    r"interview stud",
    r"case stud(?:y|ies)",
]


def today_kst() -> str:
    """Return the current date in Korea."""
    return datetime.now(KST).date().isoformat()


def normalize_doi(value: str | None) -> str:
    """Convert a DOI URL or DOI string into a normalized DOI."""
    if not value:
        return ""

    doi = value.strip()

    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break

    return doi.strip().lower()


def paper_key(paper: dict) -> str:
    """
    Return a stable paper identifier.

    OpenAlex ID is preferred because it remains usable when DOI metadata
    is later added or corrected. DOI is used as a fallback.
    """
    work_id = str(paper.get("id") or "").strip()
    if work_id:
        return f"openalex:{work_id}"

    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"

    return ""


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Reconstruct an abstract from the OpenAlex inverted index."""
    if not inverted_index:
        return ""

    words = [
        (position, word)
        for word, positions in inverted_index.items()
        for position in positions
    ]

    return " ".join(
        word for _, word in sorted(words)
    )


def classify(
    text: str,
    dictionary: dict[str, list[str]],
) -> list[str]:
    """Classify text using the configured regular-expression dictionary."""
    normalized = text.lower()

    return [
        label
        for label, patterns in dictionary.items()
        if any(
            re.search(pattern, normalized)
            for pattern in patterns
        )
    ]


def is_quantitative(
    text: str,
    methods: list[str],
) -> bool:
    """Determine whether a paper contains quantitative research signals."""
    normalized = text.lower()

    has_quant_signal = bool(methods) or any(
        re.search(pattern, normalized)
        for pattern in QUANTITATIVE_SIGNALS
    )

    qualitative_only = (
        any(
            re.search(pattern, normalized)
            for pattern in NON_QUANTITATIVE_ONLY
        )
        and not has_quant_signal
    )

    return has_quant_signal and not qualitative_only


def fetch_json(
    url: str,
    attempts: int = 4,
) -> dict:
    """Fetch JSON with retries for temporary API and network failures."""
    user_agent = "PaperRadar/1.0 (academic literature monitor)"

    if MAILTO:
        user_agent += f" mailto:{MAILTO}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent},
    )

    retryable_statuses = {
        429,
        500,
        502,
        503,
        504,
    }

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:
                return json.load(response)

        except urllib.error.HTTPError as exc:
            if (
                exc.code not in retryable_statuses
                or attempt == attempts - 1
            ):
                raise

            wait_seconds = 2 ** attempt
            print(
                f"OpenAlex HTTP {exc.code}; "
                f"retrying in {wait_seconds} seconds"
            )
            time.sleep(wait_seconds)

        except (
            urllib.error.URLError,
            TimeoutError,
        ) as exc:
            if attempt == attempts - 1:
                raise

            wait_seconds = 2 ** attempt
            print(
                f"OpenAlex network error: {exc}; "
                f"retrying in {wait_seconds} seconds"
            )
            time.sleep(wait_seconds)

    raise RuntimeError("OpenAlex request failed after all retries")


def build_openalex_url(
    journal: dict,
    start_date: str,
    cursor: str,
) -> str:
    """Build an OpenAlex cursor-pagination request URL."""
    filters = (
        f"primary_location.source.issn:{journal['issn']},"
        f"from_publication_date:{start_date},"
        "type:article"
    )

    params = {
        "filter": filters,
        "sort": "publication_date:desc",
        "per-page": str(PAGE_SIZE),
        "cursor": cursor,
    }

    if MAILTO:
        params["mailto"] = MAILTO

    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY

    return (
        "https://api.openalex.org/works?"
        + urllib.parse.urlencode(params)
    )

def fetch_elsevier_abstract(doi: str) -> str:
    """Fetch an abstract from Elsevier when OpenAlex has none."""
    if not doi or not ELSEVIER_API_KEY:
        return ""

    encoded_doi = urllib.parse.quote(doi, safe="")
    url = (
        f"https://api.elsevier.com/content/abstract/doi/{encoded_doi}"
        "?view=META_ABS"
    )

    request = urllib.request.Request(
        url,
        headers={
            "X-ELS-APIKey": ELSEVIER_API_KEY,
            "Accept": "application/json",
            "User-Agent": "PaperRadar/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)

        return (
            payload
            .get("abstracts-retrieval-response", {})
            .get("coredata", {})
            .get("dc:description", "")
            or ""
        )

    except Exception as exc:
        print(f"Elsevier abstract fallback failed for {doi}: {exc}")
        return ""


def convert_work_to_paper(
    work: dict,
    journal: dict,
    first_seen_at: str,
) -> dict | None:
    """
    Convert an OpenAlex work into a Paper Radar record.

    Papers without a selected topic or quantitative signal are excluded.
    """
    abstract = reconstruct_abstract(
    work.get("abstract_inverted_index")
)

    # OpenAlex에 abstract가 없으면 Elsevier에서 보완
    if not abstract and journal["issn"] in ELSEVIER_ISSNS:
        doi = normalize_doi(work.get("doi"))
    
        if doi:
            abstract = fetch_elsevier_abstract(doi)
    
    title = work.get("title") or "Untitled"
    combined = f"{title}. {abstract}"
    methods = classify(combined, METHODS)
    topics = classify(combined, TOPICS)
    quantitative = is_quantitative(combined, methods)

    if not topics or not quantitative:
        return None

    if not methods:
        methods = ["Other Quantitative Empirical"]

    raw_doi = work.get("doi") or ""
    doi = normalize_doi(raw_doi)

    work_id = (
        str(work.get("id") or "")
        .rsplit("/", 1)[-1]
    )

    authors = []

    for authorship in work.get("authorships", []):
        author = authorship.get("author") or {}
        display_name = author.get("display_name") or ""

        if display_name:
            authors.append(display_name)

    primary_location = work.get("primary_location") or {}
    landing_page_url = (
        primary_location.get("landing_page_url")
        or ""
    )

    openalex_url = work.get("id") or ""
    doi_url = f"https://doi.org/{doi}" if doi else ""

    return {
        "id": work_id,
        "doi": doi,
        "title": title,
        "authors": authors,
        "journal": journal["name"],
        "journal_short": journal["short"],
        "publication_date": work.get("publication_date"),
        "abstract": abstract,
        "first_seen_at": first_seen_at,
        "last_seen_at": first_seen_at,
        "methods": methods,
        "topics": topics,
        "is_quantitative": True,
        "cited_by_count": work.get("cited_by_count", 0),
        "open_access": (
            work.get("open_access", {})
            .get("is_oa", False)
        ),
        "doi_url": doi_url,
        "journal_url": (
            landing_page_url
            or doi_url
            or openalex_url
        ),
        "url": (
            doi_url
            or landing_page_url
            or openalex_url
        ),
    }


def fetch_journal(
    journal: dict,
    start_date: str,
    first_seen_at: str,
) -> tuple[list[dict], int]:
    """
    Fetch and classify recent papers from one journal.

    Returns:
        - relevant quantitative papers
        - total OpenAlex works examined
    """
    papers: list[dict] = []
    examined_count = 0
    cursor = "*"

    for page_number in range(
        1,
        MAX_PAGES_PER_JOURNAL + 1,
    ):
        url = build_openalex_url(
            journal,
            start_date,
            cursor,
        )

        payload = fetch_json(url)
        results = payload.get("results") or []

        examined_count += len(results)

        for work in results:
            paper = convert_work_to_paper(
                work,
                journal,
                first_seen_at,
            )

            if paper:
                papers.append(paper)

        meta = payload.get("meta") or {}
        next_cursor = meta.get("next_cursor")

        print(
            f"{journal['short']}: "
            f"page {page_number}, "
            f"examined {len(results)}, "
            f"matched {len(papers)}"
        )

        if not results or not next_cursor:
            break

        if len(results) < PAGE_SIZE:
            break

        cursor = next_cursor
        time.sleep(0.12)

    return papers, examined_count


def load_previous_papers() -> list[dict]:
    """Load the previously accumulated paper records."""
    if not OUTPUT.exists():
        return []

    try:
        payload = json.loads(
            OUTPUT.read_text(encoding="utf-8")
        )
    except (
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise SystemExit(
            f"Could not read existing paper data: {exc}"
        ) from exc

    papers = payload.get("papers", [])

    if not isinstance(papers, list):
        raise SystemExit(
            "Existing papers.json has an invalid papers field"
        )

    return papers


def build_existing_store(
    previous_papers: list[dict],
) -> tuple[dict[str, dict], dict[str, str]]:
    """
    Build indexes for previously saved papers.

    The DOI index prevents duplication when an OpenAlex ID changes
    or when an older record was saved without the preferred key.
    """
    store: dict[str, dict] = {}
    doi_index: dict[str, str] = {}

    for paper in previous_papers:
        key = paper_key(paper)

        if not key:
            continue

        store[key] = paper

        doi = normalize_doi(paper.get("doi"))

        if doi:
            doi_index[doi] = key

    return store, doi_index


def merge_papers(
    previous_papers: list[dict],
    fetched_papers: list[dict],
) -> tuple[list[dict], int, int]:
    """
    Merge newly fetched papers into the accumulated dataset.

    Existing papers are never removed. Updated OpenAlex metadata replaces
    old metadata, while the original first_seen_at value is preserved.
    """
    store, doi_index = build_existing_store(
        previous_papers
    )

    new_paper_count = 0
    refreshed_paper_count = 0

    fields_to_preserve_when_empty = {
        "abstract",
        "authors",
        "doi",
        "doi_url",
        "journal_url",
        "url",
    }

    for fetched in fetched_papers:
        fetched_key = paper_key(fetched)

        if not fetched_key:
            continue

        doi = normalize_doi(fetched.get("doi"))

        existing_key = None

        if fetched_key in store:
            existing_key = fetched_key
        elif doi and doi in doi_index:
            existing_key = doi_index[doi]

        if existing_key:
            existing = store[existing_key]
            merged = {
                **existing,
                **fetched,
            }

            # 논문이 Paper Radar에 최초 등록된 날짜는 변경하지 않는다.
            merged["first_seen_at"] = (
                existing.get("first_seen_at")
                or fetched.get("first_seen_at")
                or today_kst()
            )

            # OpenAlex가 일시적으로 빈 값을 반환하면 기존 값을 유지한다.
            for field in fields_to_preserve_when_empty:
                if (
                    not fetched.get(field)
                    and existing.get(field)
                ):
                    merged[field] = existing[field]

            store[existing_key] = merged
            refreshed_paper_count += 1

            if doi:
                doi_index[doi] = existing_key

        else:
            store[fetched_key] = fetched
            new_paper_count += 1

            if doi:
                doi_index[doi] = fetched_key

    all_papers = list(store.values())

    all_papers.sort(
        key=lambda item: (
            item.get("publication_date") or "",
            item.get("first_seen_at") or "",
            item.get("title") or "",
        ),
        reverse=True,
    )

    return (
        all_papers,
        new_paper_count,
        refreshed_paper_count,
    )


def main() -> None:
    run_date = today_kst()

    start_date = (
        datetime.now(KST).date()
        - timedelta(days=LOOKBACK_DAYS)
    ).isoformat()

    previous_papers = load_previous_papers()

    fetched_papers: list[dict] = []
    errors: list[dict] = []

    successful_journals = 0
    examined_work_count = 0

    for journal in JOURNALS:
        try:
            papers, examined_count = fetch_journal(
                journal,
                start_date,
                run_date,
            )

            fetched_papers.extend(papers)
            examined_work_count += examined_count
            successful_journals += 1

            print(
                f"{journal['short']}: "
                f"{len(papers)} relevant papers found"
            )

        except Exception as exc:
            errors.append({
                "journal": journal["name"],
                "error": str(exc),
            })

            print(
                f"{journal['short']}: ERROR {exc}"
            )

        time.sleep(0.12)

    # 모든 저널 검색이 실패했다면 기존 데이터를 건드리지 않는다.
    if successful_journals == 0:
        raise SystemExit(
            "Every journal fetch failed; "
            "existing paper data was not changed"
        )

    (
        all_papers,
        new_paper_count,
        refreshed_paper_count,
    ) = merge_papers(
        previous_papers,
        fetched_papers,
    )

    # 기존 데이터도 없고 새로 찾은 논문도 없다면 빈 파일을 배포하지 않는다.
    if not all_papers:
        raise SystemExit(
            "No papers are available; "
            "refusing to publish an empty feed"
        )

    now_utc = datetime.now(
        timezone.utc
    ).isoformat()

    payload = {
        "updated_at": now_utc,
        "last_checked_at": now_utc,
        "source": "OpenAlex",
        "lookback_days": LOOKBACK_DAYS,
        "query_start_date": start_date,
        "journal_count": len(JOURNALS),
        "successful_journal_count": successful_journals,
        "examined_work_count": examined_work_count,
        "fetched_matching_count": len(fetched_papers),
        "new_paper_count": new_paper_count,
        "refreshed_paper_count": refreshed_paper_count,
        "paper_count": len(all_papers),
        "errors": errors,
        "papers": all_papers,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Update completed: "
        f"{new_paper_count} new, "
        f"{refreshed_paper_count} refreshed, "
        f"{len(all_papers)} accumulated papers"
    )


if __name__ == "__main__":
    main()
