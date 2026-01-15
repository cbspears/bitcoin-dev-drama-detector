# Bitcoin Dev Drama Detector 🔥

A dashboard that tracks controversy and debate intensity across Bitcoin developer communication channels.

**Built by [Blockspace Media](https://blockspace.media)**

## What It Does

Monitors three primary Bitcoin developer communication channels and calculates "drama scores" based on sentiment analysis, reply velocity, NACK/ACK ratios, and controversial keyword detection:

- **GitHub** - bitcoin/bitcoin repository (PRs, issues, comments)
- **Mailing List** - bitcoin-dev Google Group
- **IRC** - #bitcoin-core-dev logs from gnusha.org

## Architecture

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   GitHub    │   │  Mailing    │   │    IRC      │
│    API      │   │   List      │   │   Logs      │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └────────────┬────┴────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Daily Scrapers      │
        │   (GitHub Actions)    │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Drama Analyzer      │
        │   (Claude API)        │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   JSON Data Store     │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   React Dashboard     │
        └───────────────────────┘
```

## Project Structure

```
bitcoin-dev-drama-detector/
├── scrapers/
│   ├── fetch_github.py       # GitHub API scraper
│   ├── fetch_mailing_list.py # Google Groups scraper
│   ├── fetch_irc.py          # IRC log scraper
│   └── utils.py              # Shared utilities
├── analyzer/
│   └── drama_scorer.py       # Claude API analysis
├── data/
│   ├── raw/                  # Raw scraped data
│   └── processed/            # Processed drama scores
├── dashboard/
│   └── src/                  # React dashboard
├── .github/
│   └── workflows/
│       └── daily_sync.yml    # GitHub Actions workflow
├── requirements.txt
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- GitHub Personal Access Token (for GitHub API)
- Anthropic API Key (for drama analysis)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/bitcoin-dev-drama-detector.git
cd bitcoin-dev-drama-detector
pip install -r requirements.txt
```

### Environment Variables

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"
```

### Running Scrapers Locally

```bash
# Fetch last 24 hours of data
python scrapers/fetch_github.py
python scrapers/fetch_mailing_list.py
python scrapers/fetch_irc.py
```

## GitHub Actions

The scrapers run automatically via GitHub Actions on a daily schedule. See `.github/workflows/daily_sync.yml`.

## Data Format

### daily_scores.json
```json
{
  "date": "2025-01-14",
  "overall": 7.8,
  "github": 5.1,
  "mailing_list": 8.9,
  "irc": 6.2
}
```

### threads.json
```json
{
  "id": "ml-2025-01-14-001",
  "title": "CTV activation discussion",
  "source": "mailing_list",
  "drama_score": 9.2,
  "participants": ["alice", "bob"],
  "ack_count": 7,
  "nack_count": 4
}
```

## License

MIT

## Credits

- Built by [Blockspace Media](https://blockspace.media)
- Drama detection powered by [Claude](https://anthropic.com)
