# Changelog

All notable changes to the Bitcoin Dev Drama Detector will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-15

### Added
- **BIPs Repository Tracking**: Added 4th data source tracking bitcoin/bips repository
  - New scraper `scrapers/fetch_bips.py` monitors BIPs discussions
  - Dashboard now displays BIPs drama scores with purple theme color
  - GitHub Actions workflow updated to include BIPs scraper

- **Multi-Dimensional Drama Analysis**: Replaced simple Claude API scoring with sophisticated multi-dimensional analyzer
  - **VADER Sentiment Analysis**: Converts negativity to 0-10 scale
  - **TextBlob Subjectivity Detection**: Measures opinion vs. fact ratio
  - **Politeness Theory Patterns**: Detects face-threatening acts, hedging, positive/negative politeness
  - **Speech Act Theory**: Categorizes directives, expressives, accusations, challenges
  - **Argument Quality Markers**: Evidence citations, acknowledgment, constructive proposals
  - **Fallacy Detection**: Ad hominem, strawman, appeal to authority, moving goalposts, whataboutism
  - **Special Pattern Detection**: Pile-on behavior, stonewalling, threats
  - **Participant Profiling**: Tracks individual developer communication patterns
  - New files: `analyzer/pattern_libraries.py` (310 lines), `analyzer/multi_dimensional_analyzer.py` (710 lines)
  - Updated dependencies: vaderSentiment, textblob

- **365 Days of Historical Data**: Complete year of drama scores now available
  - Date range: January 16, 2025 to January 15, 2026
  - All 4 data sources (GitHub, BIPs, IRC, Mailing List)
  - 365 daily score files with multi-dimensional analysis

- **Time Range Filters**: Chart now responds to 30d/90d/1y toggles
  - 30d: Last 30 days
  - 90d: Last 90 days
  - 1y: Full year of data

### Changed
- **Drama Index Now 7-Day Moving Average**: Main drama score displays smoothed 7-day moving average
  - Reduces volatility and noise
  - Delta compares current week to previous week
  - Added "Today" row to show current day's individual score
  - Drama alert threshold (8.0+) now based on 7d avg

- **Dashboard Data Display**: Removed placeholder/mock data
  - Chart now only displays dates with real score files
  - Previously showed fake data from Dec 16 - Jan 1

- **Dashboard UI**: Removed "LIVE DATA" badge from header

### Technical Details
- Analysis is now instant and free (no Claude API calls for scoring)
- Deterministic and explainable scores based on measurable linguistic patterns
- Average drama scores increased from 0.3/10 to 2.4/10 (more realistic detection)
- Composite score formula uses weighted dimensions (sentiment 20%, politeness 20%, face threats 15%, etc.)

### Infrastructure
- Backfilled 14 days of data with new multi-dimensional analyzer
- Re-analyzed all historical data with new scoring system
- Updated GitHub Actions workflow to include BIPs scraper

---

## [1.0.0] - 2026-01-14

### Added
- Initial release of Bitcoin Dev Drama Detector
- GitHub scraper for bitcoin/bitcoin repository
- IRC scraper for #bitcoin-core-dev logs
- Mailing list scraper for bitcoin-dev
- AI-powered drama analysis using Claude Sonnet 4
- Interactive dashboard with React + Chart.js
- GitHub Actions automation (runs every 8 hours)
- GitHub Pages deployment
- Real-time drama index with source breakdown
- Hot topics detection
- Spicy threads ranking
- Key participants tracking

### Infrastructure
- Python 3.9+ backend
- React 18 frontend (CDN)
- Chart.js 4.4.0 for visualizations
- Tailwind CSS for styling
- GitHub Pages for static hosting
