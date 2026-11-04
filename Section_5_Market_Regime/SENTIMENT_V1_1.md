# Sentiment 1.1 — optional news/social inputs

This extends [the derivatives-only v1 contract](SENTIMENT_V1.md). Existing funding,
OI and sampled liquidation calculations remain unchanged. Optional inputs are not
connected to any provider by default. No new packages, scheduled network requests,
UI changes, BUY/SELL rules, or Bias directional weights are introduced.

## Source boundary

Core owns `sentiment_external.py`, configuration/import/fetch, and a separate
`sentiment_sources.db`. Section 5 consumes only immutable, timestamped projections.
The existing bounded analytical runner obtains a read-only source snapshot per
Sentiment batch; it does not fetch the network. Recorded input bundles retain the
exact external observations even if the optional source store changes later.
New engine version 1.1.0 has separate run/state identity; prior history is retained.

A provider must emit **canonical aggregate sentiment scores** in [-1, 1]. This is a
provider-neutral integration contract, not an adapter for arbitrary vendor JSON.
A vendor-specific adapter must map its documented score semantics to this contract.
Raw headlines can be imported as UNSCORED_HEADLINE with score null; they contribute
no score. There is no keyword/NLP model pretending to infer sentiment here.

Configuration declares publisher identity/group, methodology, terms URL and an
experimental reliability fraction. Those declarations do not establish licensing
rights or validate a provider's model. Select a source, review its access/training
terms and document its score transformation before enabling it. No provider/free
tier/redistribution promise is assumed.

## Causality and classification

Only configurations and observations known by candle `as_of` are visible. Both
provider publication and local receipt times are retained; importing old data now
cannot make it available on old candles. Event revisions are append-only, ordered by
receipt rather than lexical version names. Conflicting values for an existing
revision are rejected. A later null/unscored revision cannot silently revive that
event's older score. Disabled providers disappear only after their configuration's
actual knowledge time.

Defaults (external to calculation code): news TTL 6h, social TTL 1h, neutral band
±.10, extreme band ±.60, market-wide quality multiplier .50. These are experimental
settings, not calibrated parameters. Stale, future, malformed or unscored inputs
remain unavailable. Provider scores are not a local measure of trader positioning.

Sources sharing a `publisher_group` earn one evidence contribution across both
categories. Within a category, scores are quality-weighted; category coverage is
.20 times its strongest admitted quality, never the number of duplicated providers.
NEWS and SOCIAL each retain their existing reserved .20 budget. Missing categories
are not renormalized. Opposing category scores reduce agreement and confidence;
measured neutral scores remain distinct from missing evidence. Market-wide inputs
are explicitly flagged and receive half quality by default.

Admitted external scores supply `classification.sentiment`, with scope
EXTERNAL_SENTIMENT_PARTIAL or EXTERNAL_NEWS_SOCIAL_SENTIMENT. Funding keeps its own
measurements/scope; `stability` continues to describe funding changes, not news
momentum. `positioning` remains UNKNOWN and `risk` remains the separate derivatives
stress heuristic. Extreme external labels require both independent categories and
at least .30 combined coverage. Strength is absolute normalized provider-score
intensity, not a probability. Confidence is coverage adjusted for external agreement,
not validated reliability. Maximum coverage with all current sources is .80;
normalization/account-ratio budgets remain unavailable.

## Manual setup

Use [the disabled template](examples/sentiment_provider.json) as a starting point.
Replace its placeholder terms/method/group and optional endpoint with the chosen
provider's reviewed details. Set `enabled` true only after that review. Endpoint
responses must be a JSON array matching the observation contract below. Alternatively
write a vendor-specific converter and use the local import command.

```bash
python3 sentiment_sources.py configure my_provider.json
python3 sentiment_sources.py import my_provider my_observations.json
# Optional explicit HTTPS fetch, only if configured:
python3 sentiment_sources.py fetch my_provider
python3 sentiment_sources.py status --symbol BTCUSDT
```

Each imported observation has exactly these keys (illustrative, not real data):

```json
{"event_id":"provider-window-id","revision":"1","asset":"BTCUSDT","published_ms":0,"kind":"AGGREGATE_SENTIMENT","score":0.25}
```

Use the provider's real publication time, not zero. Asset `*` means market-wide.
Receipt time is assigned locally. Imports are atomic and capped at 200 rows.
Configuration is capped at 20 provider IDs. HTTPS fetches time out at 10 seconds,
limit responses to 1 MiB, reject redirects and read credentials only from a named
environment variable. Never put tokens in configuration URLs. For header auth,
configure `auth_header`, `auth_env` (variable name only) and optional `auth_prefix`.
No automatic polling is added; arrange an explicit collector later when a provider
and cadence are selected.

## Still not implemented/validated

- Live news/social provider selection and actual credentials/connection.
- Historical funding-period normalization and verified account-ratio acquisition.
- Broad trader position/notional or forecast liquidation maps.
- Calibrated score reliability, predictive advantage or profitability.

Binance documentation access returned HTTP 403 during this implementation; no
unverified account-ratio endpoint was added. Optional source support is prepared,
not a claim that external feeds are already live.
