# Fresh Mart External Uptime Monitor

This public, credential-free code runs on GitHub-hosted infrastructure every five minutes, independently of the Fresh Mart VPS.

It checks:

- `https://freshmart.com.ng/`
- `https://shop.freshmart.com.ng/store/health`
- `https://admin.freshmart.com.ng/admin`

Each run retries three times before declaring an incident. A GitHub issue provides incident state and deduplication: one Telegram alert is sent when an incident opens and one recovery notice when it closes.

The Telegram bot credential and chat ID are stored only as GitHub Actions secrets.
