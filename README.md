# Sprachtandem Bot

Posts on a Telegram group whenever someone new joins [sprachtandem.ch](http://sprachthandem.ch).

![telegram_pic](https://i.imgur.com/pI9XyAD.png)

## Fetching details

The programs opens firefox, connects to the website, then periodically refreshes
the search page. When a new member is found, it uses a Telegram bot to post
an update to a configurable Telegram group, including details such as photo,
comments, and languages spoken and sought.

By default, the bot only searches for users interested in a either a
German-French exchange or a German-Spanish one.

To connect to firefox, [Selenium driver](https://www.selenium.dev/) is used.
The program instantiates a headless firefox instance, and uses the [Geckodriver](https://github.com/mozilla/geckodriver)
to open a webpage, fill in credentials, refresh the search page, and download
the relevant details.

The HTML code is parsed using [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/).

## Posting on Telegram

[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
is used to post updates to Telegram. This requires setting up a telegram bot
via [BotFather](https://telegram.me/BotFather).

To avoid flooding users, Telegram has placed a limitation on bots: 
they cannot send you messages until you have reached out to them yourself. In 
practice, this means you need to send the message `/schedule` to the bot you
registered before it can post updates in the group.

## Persistence

A list of users already seen are stored in `sprachtandem.db` in the working
directory. This prevents the bot from re-posting already-seen users when
restarting.
