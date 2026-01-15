# Bitcoin Dev Drama Detector

**Live Dashboard:** Monitoring drama levels in Bitcoin development discussions

## What is this?

An AI-powered system that analyzes Bitcoin developer discussions across GitHub, IRC, and mailing lists to detect controversial topics and measure community sentiment.

## Current Drama Level

Check the dashboard above for real-time drama scores!

## Data Sources

- **GitHub**: bitcoin/bitcoin repository (PRs, issues, comments)
- **IRC**: #bitcoin-core-dev channel logs from gnusha.org
- **Mailing List**: bitcoin-dev from gnusha.org

## How It Works

1. **Data Collection**: Automated scrapers run every 8 hours
2. **AI Analysis**: Claude Sonnet 4 analyzes content for drama signals
3. **Visualization**: Interactive dashboard shows trends and hot topics

## Metrics

- **Drama Score** (0-10): Overall controversy level
- **Hot Topics**: Trending discussion subjects
- **Spicy Threads**: Most contentious conversations
- **Key Contributors**: Most active participants

## Technology

- Python scrapers with AI analysis (Anthropic API)
- React dashboard with Chart.js
- GitHub Actions for automation
- Deployed on GitHub Pages

---

Built with ❤️ and AI by [Blockspace Media](https://blockspace.media)
