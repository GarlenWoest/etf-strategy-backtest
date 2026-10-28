# Paper-trading options for the USD/JPY workflow (2026-10-28)

_Read-only research from official documentation. No account was opened, no API was called, and no credentials were seen. "Not stated" means the official page read didn't say. Raw prices aren't quoted._

| | **OANDA practice (v20 API)** | **Alpaca paper** | **IBKR paper** | **Internal simulator** (ours) |
|---|---|---|---|---|
| Instruments relevant to us | FX (OANDA US lists "over 68 major and minor currency pairs"; USD/JPY is one). Gold/metals: **not listed on the US pages read** (only forex and crypto) | US stocks and ETFs (GLD included); crypto. **No FX found** in the official docs | FX via IDEALPRO/IDEAL; stocks and ETFs; futures (permissions needed) | Anything we have prices for (USD/JPY via the market snapshot) |
| US eligibility | OANDA US offers live and practice accounts; demo sign-up asks for country of residence and personal details | Paper-only account: "Anyone globally … with your email address" | Only existing clients; "A paper trading account will not be opened until your account has been funded" | n/a |
| Minimum size | "as low as 1 unit" (FX) | Fractional ETFs from $1 (market orders, regular hours) | IDEALPRO standard minimum about USD 25,000 equivalent (JPY 2,500,000); smaller orders are odd lots on IDEAL with different pricing (IBKR order-size page via search; the page itself returned 403 to the reader) | Any size |
| Quote quality | OANDA's own dealer prices; "Usually, the demo price feed is the same as the live account price feed" | NBBO matching; a paper-only account gets **IEX data only**; partial fills simulated 10% of the time | Top of book; paper accounts inherit the live account's market-data subscriptions | Yahoo indicative last price (not executable; bid/ask rejected as inconsistent) |
| Costs modelled | Spread-only, or core pricing plus commission (core needs a USD 10k+ balance); financing from tom-next swap rates plus a holding charge; 1.0% conversion fee on non-home-currency trades | Commission-free equities; **not simulated:** slippage, market impact, queue position, regulatory fees, dividends | Commission about 0.2 bp of trade value with a USD 2 minimum (current pricing page; older PDFs say USD 2.50) | Our assumption: 0.015% one-way plus a 0.75%/yr markup (unverified) |
| Credentials needed | Personal access token from the account portal (valid for the whole account). It would stay with you; rule 1 forbids Claude handling it | API key pair for the paper account | Paper username and password, plus TWS or IB Gateway running | None |
| API limits | 120 requests/s; 20 streams; 2 new connections/s; practice REST base `api-fxpractice.oanda.com` | Not stated on the page read | TWS/Gateway session; some order types unsupported in paper | None |
| Main limitations | No gold for US clients on the pages read; practice fills aren't real fills; a token gives access to the whole practice account, not read-only pricing | Can't trade USD/JPY at all; IEX-only data | Funded live account first; $1M default paper equity; odd-lot FX pricing differs at our sizes; highest setup burden | Indicative prices only; costs and spreads unverified; no execution realism |

## Recommendation

1. **Now: the internal simulator.** It needs no account, no credentials and no new software, and it reuses fx_engine_v2's accounting. It keeps the project's "no broker" rule intact. Its weakness, unverified costs, is stated in every report.
2. **Next, if you approve a broker step: an OANDA practice account used read-only for pricing.** It's the only option that covers USD/JPY with executable-style bid/ask from 1 unit, at no cost, and its practice feed is "usually" the live feed. That makes it the cheapest way to measure real spreads and swap rates against our 0.015% and 0.75%/yr assumptions.

**Conditions for the OANDA step:**
- You open the account and hold the token, which is read from an environment variable and never printed, logged or committed (as with the FRED key).
- The adapter calls only pricing endpoints, never order endpoints, and a test enforces that.
- It needs your separate approval, because the project currently prohibits broker connectivity.

**Not recommended:**
- **Alpaca:** no FX.
- **IBKR:** needs a funded live account; its FX minimums and odd-lot pricing don't fit a small learning account.

Sources: [OANDA v20 introduction](https://developer.oanda.com/rest-live-v20/introduction/), [OANDA development guide](https://developer.oanda.com/rest-live-v20/development-guide/), [OANDA US account comparison](https://oanda.com/us-en/trading/account-comparison), [OANDA US minimum trade size](https://help.oanda.com/us/en/faqs/minimum-trade-size.htm), [OANDA US demo account](https://help.oanda.com/us/en/faqs/open-demo-account.htm), [OANDA US charges](https://www.oanda.com/us-en/trading/our-charges/), [Alpaca paper trading](https://docs.alpaca.markets/docs/paper-trading), [Alpaca fractional trading](https://docs.alpaca.markets/us/docs/fractional-trading), [IBKR paper accounts](https://www.ibkrguides.com/clientportal/aboutpapertradingaccounts.htm), [IBKR spot currency order sizes](https://www.interactivebrokers.com/en/trading/forexOrderSize.php), [IBKR pricing](https://www.interactivebrokers.com/en/whyib/low-trading-cost.php), [IBKR odd lots FAQ](https://www.ibkrguides.com/kb/article-1708.htm).
