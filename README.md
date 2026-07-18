# DailyCrosswordBot

A GitHub Actions bot that automatically grabs a "Play Together" link from the LA Times daily crossword and emails it to a group of recipients twice a day.

## Why

So that me and my friends can do the crossword every day without having to wonder what time everybody else is going to be doing it :)

## How

1. An obfuscated Playwright headless browser generates the URL for the daily browser and navigates there
2. It performs a series of actions to obtain a shareable link (including blocking ads, otherwise you have to wait 30 seconds for the link)
3. It emails the link to a group of recipients
4. GitHub Actions executes this on a schedule, using a cached image in order to speed up execution.

## Setup

1. Fork/clone repo
2. Create a dedicated gmail account for the bot, enable 2FA, and generate an [App Password](https://myaccount.google.com/apppasswords)
3. Add the following variables as GitHub secrets:
   - `GMAIL_USER` (email address)
   - `GMAIL_APP_PASSWORD` — the app password
   - `RECIPIENTS` — comma-separated list of recipient emails
4. Adjust the cron schedule in `.github/workflows/crossword.yml` to your desired schedule, or trigger manually from the Actions tab as a `workflow_dispatch` (good to validate the action is set up correctly)
