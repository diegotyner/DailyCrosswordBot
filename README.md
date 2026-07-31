# DailyCrosswordBot

A daily bot that automatically grabs a "Play Together" link from the LA Times daily crossword and emails it to a group of recipients twice a day. Configured to work on an AWS EC2 VM, or for free with GitHub Actions.

> GitHub Actions ran too inconsistently (timewise) for my use case, so I refactored the code to run on AWS under an EC2 VM. It also gave me the freedom to expand the project with SQLite statistics which was another reason I steered away from GA.

For the GitHub Actions variant of the code: checkout the `GithubActions_Archive` branch and use that to run the scraper. It should work like a charm after configuring your GitHub secrets.

## Why

So that me and my friends can do the crossword every day without having to wonder what time everybody else is going to be doing it :)

## How

1. An obfuscated Playwright headless browser generates the URL for the daily browser and navigates there
2. It performs a series of actions to obtain a shareable link (including blocking ads, otherwise you have to wait 30 seconds for the link)
3. It emails the link to a group of recipients
4. GitHub Actions executes this on a schedule, using a cached image in order to speed up execution.

## Setup

For each of the following, you'll need to have an updated installation of python and it is recommended to have venv up to date as well.

- Activate venv: `python -m venv .venv` -> `source .venv/bin/activate`
- Install dependencies (from root): `pip install -r requirements.txt`
- ADDITIONALLY, install a browser for playwright: `playwright install --with-deps chromium`

### AWS EC2

1. Fork/clone repo
2. Create a dedicated gmail account for the bot, enable 2FA, and generate an [App Password](https://myaccount.google.com/apppasswords)
3. Add a `.env` file with the following variables in the project root:
   - `GMAIL_USER` (email address)
   - `GMAIL_APP_PASSWORD` — the app password
   - `RECIPIENTS` — comma-separated list of recipient emails
4. Create a cron schedule for execution.
   - I've provided a sane default for a script you can point at (which requires a venv installation): `run_crossword.sh`.
   - Then you'll have to configure the cronjob, the sample below runs my script at 12pm and 4pm. Make sure to use absolute paths, and remember to set it correctly to the EC2's timezone.
     - `crontab -e` -> `0 12,16 * * * /path/to/DailyCrosswordBot/run_crossword.sh >> /path/to/DailyCrosswordBot/logs/cron_stdout.log 2>&1`

### GitHub Actions

1. Fork/clone repo, but switch to the archive branch: `git checkout GithubActions_Archive`
2. Create a dedicated gmail account for the bot, enable 2FA, and generate an [App Password](https://myaccount.google.com/apppasswords)
3. Add the following variables as GitHub secrets:
   - `GMAIL_USER` (email address)
   - `GMAIL_APP_PASSWORD` — the app password
   - `RECIPIENTS` — comma-separated list of recipient emails
4. Adjust the cron schedule in `.github/workflows/crossword.yml` to your desired schedule, or trigger manually from the Actions tab as a `workflow_dispatch` (good to validate the action is set up correctly)
   - Bear in mind that GitHub Actions timing depends on demand, it won't actually be on time. When I tested it, it ran fairly consistently one hour after I scheduled it
