from selenium import webdriver

try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
import logging
import os
import pickle
import sys
import telegram.ext

FRENCH = 16
GERMAN = 10
ZURICH = 23
SPANISH = 48
BOT_TOKEN = '<complete here>'
TELEGRAM_GROUP_ID = '<complete here>'
DB_PATH = 'sprachtandem.db'
LANG_PAIRS = [(FRENCH, SPANISH), (FRENCH, GERMAN), (SPANISH, GERMAN)]
URL_BASE = 'http://sprachtandem.ch{}'
LOGIN_PAGE = 'http://sprachtandem.ch/en/login'
USERNAME = '<complete here>'
PASSWORD = '<complete here>'
LOGIN_FORM = '//form[1]'

interval = 3600

logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
mq = None
driver = None
db = set()


class profile(object):
    def __init__(self, html):
        self.html = html
        self.name = self.html.find('p', attrs={'class': 'name'}).string
        ots = self.html.find_all('p', attrs={'class': 'overtitle'})
        for o in ots:
            if o.string != 'About me':
                continue
            self.desc = o.next_sibling.string

    def target_languages(self):
        languages = self.html.find_all('div', attrs={'class': 'user_langs'})
        for lang in languages:
            type = lang.find('p', attrs={'class': 'overtitle'})
            if type.string != 'target language':
                continue
            return [tl.string for tl in type.next_siblings]
        return []

    def id(self):
        return int(self.html.find(
                'a', attrs={'class': 'button'})['data-userprofile'])

    def link(self):
        return URL_BASE.format(
                self.html.find('a', attrs={'class': 'button'})['href'])

    def img(self, driver=None):
        if not driver:
            return URL_BASE.format(self.html.find('img')['src'])

        driver.get(self.link())
        html = BeautifulSoup(driver.page_source, 'html.parser')
        if not html:
            return None
        prf = html.find('div', attrs={'class': 'image'})
        return URL_BASE.format(prf.find('img')['src'])

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, profile) and (self.name == other.name)


def parseProfiles(driver, html):
    lst = set()
    for prf in html:
        lst.add(profile(html=prf))
    return lst


def login(driver, page, id_username, username, id_pwd, pwd, id_form):
    assert driver is not None
    driver.get(page)
    login = driver.find_element_by_id(id_username)
    login.clear()
    login.send_keys(username)
    password = driver.find_element_by_id(id_pwd)
    password.clear()
    password.send_keys(pwd)
    form = driver.find_element_by_xpath(id_form)
    form.submit()


def search(driver, src, dst, loc):
    driver.get('http://sprachtandem.ch/en/search/{}/{}/{}'.format(
        src, dst, loc))
    html = BeautifulSoup(driver.page_source, 'html.parser')
    profilesHtml = html.body.find_all(
            'div', attrs={'class': 'profile clearfix'})
    return parseProfiles(driver, profilesHtml)


def loadDB(path):
    global db
    with open(path, 'rb') as f:
        data = pickle.load(f)
        logging.info('Loading DB with {} profiles'.format(len(data)))
        db.update(data)


def saveDB(path):
    global db
    with open(path, 'wb') as f:
        pickle.dump(db, f)


def scrape_and_update(context):
    global mq
    global driver
    global db

    newProfiles = set()
    for (ori, dst) in LANG_PAIRS:
        lst = search(driver, ori, dst, ZURICH)
        for p in lst:
            if p.id() in db:
                continue
            newProfiles.add(p)

    logging.info('found {} new profiles'.format(len(newProfiles)))
    for p in newProfiles:
        id = p.id()
        if id in db:
            continue
        txt = '{} ({}): {}\n{}'.format(
                p.name, ','.join(p.target_languages()), p.desc, p.link())
        logging.info('Getting img from {} ({})'.format(p.name, p.link()))
        img = p.img(driver)
        if img:
            prms = telegram.ext.utils.promise.Promise(
                    pooled_function=context.bot.send_photo, args=[],
                    kwargs={
                        'chat_id': TELEGRAM_GROUP_ID,
                        'photo': img,
                        'caption': txt})
        else:
            prms = telegram.ext.utils.promise.Promise(
                    pooled_function=context.bot.send_message, args=[],
                    kwargs={
                        'chat_id': TELEGRAM_GROUP_ID,
                        'text': txt})
        mq(prms, is_group_msg=True)
        db.add(id)

    logging.info('Saving DB of size {}'.format(len(db)))
    saveDB(DB_PATH)


def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def schedule(update, context):
    scrape_and_update(context)
    context.job_queue.run_repeating(scrape_and_update, interval)


def main(argv):
    global mq
    global driver

    # Initialize the DB
    if os.path.exists(DB_PATH):
        loadDB(DB_PATH)

    # Initialize the driver
    opts = webdriver.firefox.options.Options()
    opts.set_headless()
    driver = webdriver.Firefox(options=opts)
    login(driver, page=LOGIN_PAGE, id_username='id_email', username=USERNAME,
            id_pwd='id_password', pwd=PASSWORD, id_form=LOGIN_FORM)
    logging.info('logged in.')

    # Initialize the message queue
    mq = telegram.ext.MessageQueue(
            group_burst_limit=15,
            group_time_limit_ms=50000)

    # Initialize the bot
    persistence = telegram.ext.PicklePersistence(DB_PATH)
    updater = telegram.ext.Updater(
            BOT_TOKEN, use_context=True, persistence=persistence)
    dp = updater.dispatcher
    dp.add_handler(telegram.ext.CommandHandler(
        'schedule', schedule, pass_job_queue=True))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()
    driver.close()


if __name__ == '__main__':
    main(sys.argv[1:])
