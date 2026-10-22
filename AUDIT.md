# Phase 0 security audit: day-trader-skill

| | |
|---|---|
| Repository | https://github.com/Jakeschincariol/day-trader-skill |
| Commit audited | `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd` (branch `main`, committed 2026-10-20T09:17:50-05:00) |
| Clone location | `trading-research/vendor/day-trader-skill` (excluded from our git via `.gitignore`, made read-only) |
| Audit date | 2026-10-22 |
| Method | Static reading only. No code, tests, installers or plugins were run. Fixtures were inspected as data with isolated Python (`python3 -I`), outside the repo. |

## Verdict: SAFE WITH CAVEATS

The code does what it says. Nothing in it is malicious: no obfuscation, no exfiltration, no hidden execution, no hooks, no prompt injection. The caveats come from what it is built for, not from hidden behavior:

1. It is a day-trading plugin for individual stocks, with an order-placing skill (`trader-broker`). Installing the plugin would load all 11 skills, including one that tells Claude to call a broker's order tool. That breaks our Hard Rule 1. **Do not install it, as a plugin or as copied skills.**
2. It contacts two domains not on your expected list: `feeds.finance.yahoo.com` and `stooq.com`. Both are benign public data sources.
3. Several skills tell Claude to run long-lived background watchers or `/loop` jobs. That doesn't fit our end-of-day workflow.
4. Almost nothing in it fits our task (end-of-day swing research on 8 ETFs). The reuse list below is very short.

## a. Provenance and git history

- One commit in the whole history: `3d0f4ef` "The Trader skill v2: 11 day-trading skills", author Jake Schincariol, dated 2026-10-20, two days before this audit. It has a `Co-Authored-By: Claude Opus 5.5` trailer, so the code is largely AI-generated.
- The history was squashed, so there are no earlier commits to review. `git rev-list --all --objects` gives 112 objects: 85 blobs, the trees and 1 commit. No unreachable objects.
- The remote also has two unmerged pull requests (`refs/pull/2/head` = `458e10f`, `refs/pull/4/head` = `27d8cfb`). They are **not** in our clone and were not audited. We do not use them.
- `.git/hooks` contains only the stock `*.sample` files, none active. No symlinks. No executable bits on any file.

## c. Every file, with size (bytes)

85 files tracked. Hidden folders: only `.claude-plugin/`.

```
787     .claude-plugin/marketplace.json
665     .claude-plugin/plugin.json
1073    LICENSE                                   (MIT)
11216   README.md
8204    trader-alerts/SKILL.md
597     trader-alerts/alerts.example.json
32825   trader-alerts/alerts.py
5943    trader-analyst/SKILL.md
23996   trader-analyst/facts.py
2317    trader-analyst/metrics.example.json
11451   trader-broker/SKILL.md
378     trader-broker/claude_desktop_config.example.json
32390   trader-broker/ticket.py
8629    trader-budget/SKILL.md
595     trader-budget/config.example.json
39238   trader-budget/size.py
610     trader-budget/targets.example.json
7715    trader-entry/SKILL.md
42324   trader-entry/entry.py
6987    trader-exit/SKILL.md
31107   trader-exit/exit.py
5346    trader-news/SKILL.md
22467   trader-news/news.py
7395    trader-pelosi/SKILL.md
22928   trader-pelosi/ptr.py
9608    trader-risk/SKILL.md
39151   trader-risk/check.py
10940   trader-scanner/SKILL.md
47679   trader-scanner/scan.py
9624    trader-timemachine/SKILL.md
43070   trader-timemachine/timemachine.py
468     tests/_load.py
22688   tests/test_alerts.py
7404    tests/test_analyst.py
15409   tests/test_broker.py
18047   tests/test_budget.py
29666   tests/test_entry.py
14278   tests/test_exit.py
10001   tests/test_news.py
9490    tests/test_pelosi.py
6655    tests/test_repo.py
27559   tests/test_risk.py
35881   tests/test_scanner.py
32237   tests/test_timemachine.py
109     tests/fixtures/trader-alerts/stooq-AAPL.csv
80      tests/fixtures/trader-alerts/stooq-ZZZZ.csv
1297    tests/fixtures/trader-alerts/yahoo-AAPL.json
1307    tests/fixtures/trader-alerts/yahoo-AXP.json
1325    tests/fixtures/trader-alerts/yahoo-BAC.json
1304    tests/fixtures/trader-alerts/yahoo-GOOGL.json
1308    tests/fixtures/trader-alerts/yahoo-KO.json
2875    tests/fixtures/trader-alerts/yahoo-TSLA.json
109     tests/fixtures/trader-alerts/yahoo-ZZZZ.json
1890    tests/fixtures/trader-analyst/000032019326000018/index.json
223     tests/fixtures/trader-analyst/company_tickers.json
6616    tests/fixtures/trader-analyst/companyfacts-CIK0000021344.json
26050   tests/fixtures/trader-analyst/companyfacts-CIK0000320193.json
3662    tests/fixtures/trader-analyst/submissions-CIK0000021344.json
5105    tests/fixtures/trader-analyst/submissions-CIK0000320193.json
1183    tests/fixtures/trader-budget/berkshire-q2-2026-top5.json
504     tests/fixtures/trader-budget/plan-tsla.json
2061    tests/fixtures/trader-entry/DEMO-1m-synthetic.json
2789    tests/fixtures/trader-entry/TSLA-2026-10-19-5m.json
2072    tests/fixtures/trader-news/chart-TSLA.json
532     tests/fixtures/trader-news/company_tickers.json
6972    tests/fixtures/trader-news/sec-8-K-0000021344.xml
7456    tests/fixtures/trader-news/sec-8-K-0000320193.xml
4313    tests/fixtures/trader-news/yahoo-AAPL.xml
3157    tests/fixtures/trader-news/yahoo-KO.xml
12062   tests/fixtures/trader-news/yahoo-TSLA.xml
716     tests/fixtures/trader-pelosi/2026FD.zip             (binary: ZIP holding one 4,460-byte XML)
3592    tests/fixtures/trader-pelosi/ptr-20033725-excerpt.txt
4596    tests/fixtures/trader-pelosi/ptr-20035143.txt
3446    tests/fixtures/trader-pelosi/ptr-20035562-excerpt.txt
2165    tests/fixtures/trader-pelosi/ptr-20035590.txt
757     tests/fixtures/trader-risk/orders-reel.json
922     tests/fixtures/trader-risk/orders-tsla.json
1986    tests/fixtures/trader-scanner/TSLA-5m-live-2026-10-20-1001.json
44322   tests/fixtures/trader-scanner/daily-spark-2026-10-19.json
42905   tests/fixtures/trader-scanner/spark-3mo-live-2026-10-20.json
28175   tests/fixtures/trader-scanner/spark-5m-live-2026-10-20-1001.json
1384    tests/fixtures/trader-scanner/symdir/nasdaqlisted.txt
1728    tests/fixtures/trader-scanner/symdir/otherlisted.txt
65951   tests/fixtures/trader-scanner/wall5m-2026-10-19.json.gz  (binary: gzip of 349,131-byte JSON)
92941   tests/fixtures/trader-timemachine/TSLA-60d5m.json.gz     (binary: gzip of 414,569-byte JSON)
```

**What "read in full" covered:** every `.py`, `SKILL.md`, manifest, example config, README and LICENSE, line by line, and every small text fixture (CSV, symbol directories, example JSON). The large numeric fixtures (Yahoo chart/spark JSON, SEC XBRL JSON, RSS/Atom XML, PTR text) and the three binary archives were checked by structure and content: decompressed and parsed as data, scanned for instruction-like text, script tags, encoded payloads and non-printable or hidden Unicode characters. That scan found nothing. I did not read every number in the price fixtures one by one.

## d. Plugin manifest: hooks, MCP servers, auto-run commands

| Finding | File:line | Severity |
|---|---|---|
| No `hooks`, no `mcpServers`, no `commands`, no install scripts in either manifest. Nothing runs on install or on tool use. | `.claude-plugin/plugin.json:1-22`, `.claude-plugin/marketplace.json:1-18` | None |
| `"skills": "./"` loads **all 11** skill folders at once. That includes `trader-broker`, whose instructions lead to broker order calls. | `.claude-plugin/plugin.json:21` | Medium (policy): reason not to install |
| An example Claude Desktop MCP config starts `uvx alpaca-mcp-server`, a third-party package downloaded from PyPI at run time, and passes broker API keys in env vars. It is only an example and is never applied automatically. If anyone copied it into their Claude Desktop config, it would download and run outside code with brokerage access. | `trader-broker/claude_desktop_config.example.json:1-14`; walkthrough in `trader-broker/SKILL.md:58-116` | Medium (policy): never use |

## e. Dangerous-pattern search (all `.py`)

| Pattern | Result |
|---|---|
| `subprocess` | **One use:** `trader-pelosi/ptr.py:337-345` runs `pdftotext -layout <pdf> -` with an argument list (no shell, no string interpolation) and a 60 s timeout. The binary is found with `shutil.which` on `PATH`, so a hostile `pdftotext` placed earlier on `PATH` would run. Low risk. Not reused. |
| `os.system`, `os.popen`, `exec(`, `eval(`, `compile(`, `__import__`, `pickle`, `marshal`, `base64`, `codecs`, `socket`, `http.client`, `requests`, `ctypes` | None. (`re.compile` is regex only.) |
| `importlib` | `tests/_load.py:3-15` only: loads the repo's own tool scripts by path for the tests. |
| `urllib` | `urllib.request`/`urllib.error` (GET only, fixed URL templates) in `scan.py:229-267, 854`, `entry.py:254-299`, `exit.py:338-382`, `timemachine.py:188-234`, `alerts.py:249-298`, `news.py:160-191`, `facts.py:92-122`, `ptr.py:82-90`. No POST, no uploads. |
| `shutil.rmtree`, `os.remove` | Tests only, on temp dirs they created themselves: `test_entry.py:496`, `test_timemachine.py:514,527`, `test_alerts.py:133,334`, `test_scanner.py:486`, `test_broker.py:119`, `test_exit.py:145,229,247`. |
| `open(...,"w"/"wb")` | All write to relative `trader/...` paths under the current directory, or to a path the user passes: `alerts.py:359`, `facts.py:537`, `ticket.py:132`, `size.py:767`, `entry.py:576`, `exit.py:659`, `news.py:539`, `ptr.py:177,465`, `check.py:807`, `scan.py:829,864`, `timemachine.py:865`. Several use atomic tmp + `os.replace`. |
| Environment variables | `SEC_USER_AGENT` only (`news.py:149`, `facts.py:80`). Its value (your name + email, which SEC requires) is sent only to sec.gov. |
| `~/.ssh`, `~/.aws`, browser data, keychains, credentials, home dir | None. Nothing reads or writes outside the working directory. |

Path-handling nit (low): `ptr.py:458-466` builds a file name from a DocID taken from the CLI or the House XML index without sanitizing it. A malformed DocID containing `../` could write a file outside `trader/state/ptr-pdfs/`. The download must start with `%PDF`, and the source is the House Clerk. Not reused.

## f. Every URL and domain contacted by code

| Domain | Where | On expected list? |
|---|---|---|
| `query1.finance.yahoo.com`, `query2.finance.yahoo.com` | `scan.py:83`, `entry.py:269`, `exit.py:352`, `timemachine.py:189`, `alerts.py:63,201`, `news.py:56` | Yes |
| `www.nasdaqtrader.com` | `scan.py:85` | Yes |
| `www.sec.gov`, `data.sec.gov` | `news.py:57,59`; `facts.py:53-56` | Yes (sec.gov) |
| `disclosures-clerk.house.gov` | `ptr.py:48-50` | Yes |
| **`feeds.finance.yahoo.com`** | `news.py:55` (headline RSS) | **No: flagged.** Benign public Yahoo feed. |
| **`stooq.com`** | `alerts.py:197` (optional quote source, `--source stooq`) | **No: flagged.** Benign. The code itself says Stooq answered 404 on 2026-10-13 (`alerts.py:38-39`). |

Not contacted by code, only mentioned in docs, comments or the User-Agent string: `github.com` (UA string `scan.py:82`, `news.py:61`, etc.), `nyse.com` (source comment), `efdsearch.senate.gov` (manual instructions; the skill explicitly does not automate it), `api.ibkr.com/v1/api/mcp` (`trader-broker/SKILL.md:130`, a connector the user would add), `opusjake.ai` (author URL in the manifests), `docs.astral.sh` (install instructions).

Note: most Yahoo requests send a browser-style User-Agent, `Mozilla/5.0 (compatible; day-trader-skill/2.0; +github...)` (`scan.py:82`, `news.py:61`). The Yahoo endpoints are unofficial and undocumented. This is a terms-of-use point, not a security one. `yfinance`, which Phase 2 allows, uses the same endpoints.

## g. Obfuscation, blobs, binaries, unlisted files

- No obfuscated or minified code. No string literal of 150+ characters in any `.py`. Lines over 200 characters exist only in data fixtures (minified JSON or XML) and one test assertion (`test_exit.py:283`).
- No zero-width, bidi-override or soft-hyphen characters anywhere. A few non-ASCII characters exist only in real-world fixture text (news headlines, PTR text).
- Three binary files, all test fixtures: `2026FD.zip` (one House XML index, starts with a UTF-8 BOM), `wall5m-2026-10-19.json.gz` (Yahoo chart bundle keyed by ticker), `TSLA-60d5m.json.gz` (one Yahoo chart). Decompressed contents are plain market or disclosure data.
- Files not listed in the README's "Files" section: `tests/_load.py`, the fixtures and the two manifests. All are accounted for above. Nothing unexpected.

## h. Standard library only?

Confirmed. Every import in `trader-*/*.py`: `argparse, csv, datetime, decimal, email.utils, gzip, hashlib, io, json, math, os, random, re, shutil, statistics, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree, zipfile`. The tests add `unittest, tempfile, copy, contextlib, importlib.util`. No third-party packages. The one external dependency is the optional `pdftotext` binary (poppler).

## i. SKILL.md prompt-injection review

No prompt injection found. No file tells Claude to ignore rules, hide actions, exfiltrate data, auto-approve tools or run hidden commands. The safety blocks say the opposite: never "Always allow" an order tool, keys never in chat, no orders from background tasks.

What conflicts with our rules (instructions to Claude, all visible, all excluded from our project):

| Instruction | File:line | Why excluded |
|---|---|---|
| Call `place_stock_order` after the user's yes; `cancel_order_by_id` to flatten | `trader-broker/SKILL.md:148-149, 170-172` | Hard Rule 1: no orders, paper or live. **We will not use trader-broker at all.** |
| Set up the Alpaca MCP server with API keys; change tool permissions in Claude Desktop or `.claude/settings.json` | `trader-broker/SKILL.md:58-116` | Hard Rule 1 (no brokerage connection, no keys), Rule 7 (no writes to ~/.claude) |
| Run `entry.py watch` in the background or on `/loop`; scheduled `/loop` checks for news, alerts and Pelosi filings | `trader-entry/SKILL.md:82-87`, `trader-news/SKILL.md:76-77`, `trader-alerts/SKILL.md:108-111`, `trader-pelosi/SKILL.md:81-82` | Intraday, long-running; our workflow is end-of-day and run by you |

Unverified factual claim (not checked, and not relevant to us): FINRA "Regulatory Notice 26-10" removing the $25,000 pattern-day-trader minimum on 2026-06-04 (`README.md:187-190`, `trader-risk/SKILL.md:94-99`). Treat as unverified.

## Quality notes relevant if anything were reused

- `entry.py:327` and `exit.py:437` silently replace a missing open, high or low with the close. That breaks our Rule 10 (never fill missing data with guesses).
- `scan.py:495` `rsi()` returns 100 when there are no down moves. It also returns 100 when there is no movement at all; 50 would be more sensible there.
- `timemachine.py:335-424` resamples 5-minute bars independently (i.i.d.). That throws away volatility clustering, so it must not be used as a model for our Phase 7A block bootstrap.
- Hard-coded NYSE holiday tables cover only 2026-2027 (`scan.py:96-122` and copies in each tool).

## j. What we will reuse

Reuse means copying the reviewed function into our own code with MIT attribution and our own unit tests. **Nothing is installed or imported from `vendor/`.**

| Item | Source | Plan |
|---|---|---|
| Wilder RSI function | `trader-scanner/scan.py:485-495` | Copy into `src/strategies.py` for the RSI(2) strategy. Add a test against Wilder's textbook example (70.46, as in `tests/test_scanner.py:300-305`). Change the flat-series case to return 50. Will be vectorized for pandas. |
| NYSE 2026-2027 holiday and early-close table | `trader-scanner/scan.py:96-122` | Optional, Phase 8 only: lets `daily_signal.py` name the next trading day. Verify against nyse.com first. |
| Ideas only (no code) | timemachine verdict logic; seed reporting | Report results against a break-even benchmark, and print the random seed with every simulated number. |

**Not reused:** `trader-broker` (never), `trader-risk`, `trader-budget`, `trader-entry`, `trader-exit`, `trader-timemachine` simulation, `trader-alerts`, `trader-news`, `trader-analyst`, `trader-pelosi`, the Yahoo fetch code (Phase 2 uses `yfinance`), and both example configs.

**Heads-up for Phase 2:** the repo itself reports Stooq's quote CSV answering 404 on 2026-10-13. If Stooq's historical download is also down when we get there, I will stop and ask you which second source to use for the cross-check, rather than skipping it.
