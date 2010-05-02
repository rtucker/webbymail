#!/usr/bin/python

# webbymail: a script to retrieve URLs via mail
# Ryan Tucker <rtucker@gmail.com>, 2010/05/02

__USERAGENT__ = "webbymail/0.01alpha1 +http://github.com/rtucker/webbymail/"
__SENDER__ = "webbymail@hoopycat.com"

import email
import logging
import logging.handlers
import smtplib
import sys
import urllib2
import urlparse

from email import encoders

from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Set up syslog
logger = logging.getLogger('')
loghandler = logging.handlers.SysLogHandler('/dev/log',
                facility=logging.handlers.SysLogHandler.LOG_DAEMON)
logformatter = logging.Formatter('%(filename)s: %(levelname)s: %(message)s')
loghandler.setFormatter(logformatter)
logger.addHandler(loghandler)

logger.setLevel(logging.DEBUG)

class UnauthorizedUserError(Exception):
    """Raised when an unauthorized e-mail address e-mails us"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class InvalidUrlError(Exception):
    """Raised when a URL isn't valid, or fails to parse or whatnot"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def verify_allowed_user(email):
    """
    Checks the sender's e-mail address to ensure they're allowed to use this
    service.
    """
    if email in ['rtucker@gmail.com']:
        return True

    return False

def verify_url(url):
    """
    Checks to ensure the URL is a valid method and isn't too dodgy.
    """
    parsed = urlparse.urlparse(url)

    if parsed.scheme not in ['http', 'https']:
        raise InvalidUrlError, "Unacceptable scheme: " + parsed.scheme

    if parsed.port not in [None, 80, 443]:
        raise InvalidUrlError, "Unacceptable port: %i" + parsed.port

    return parsed.geturl()

def handle_mail_pipe(fd):
    """
    Handles a piped message in from the MTA, returning a list of URLs to fetch.
    """

    msg = email.message_from_file(fd)

    if msg.get('Message-Id'):
        logger.info("Processing Message-ID " + msg.get('Message-Id'))
    else:
        logger.error("Processing message with no Message-ID!")

    logger.debug("Headers found in mail: " + msg.keys())

    # Check user permissions
    if not msg.get('From'):
        raise KeyError, "No From: header found!"
    if not verify_allowed_user(msg.get('From')):
        logger.error("Unauthorized usage from " + msg.get('From'))
        raise UnauthorizedUserError, "Not allowed to accept mail from " + msg.get('From')

    # Check the Subject: header for the URL to fetch
    if not msg.get('Subject'):
        raise KeyError, "No Subject: header found!"

    return (msg.get('From'), [verify_url(msg.get('Subject'))])

def fetch_url(url):
    """
    Fetches a URL and returns a tuple of (Content-type, raw data)
    """

    # Set our headers
    headers = {
        'User-Agent': __USERAGENT__
    }

    # Check the URL is valid and open it
    logger.debug('Attempting open of ' + url)
    req = urllib2.Request(verify_url(url), headers=headers)
    response = urllib2.urlopen(req)
    contenttype = response.info().getheader('Content-type', 'application/octet-stream')
    data = response.read()

    logger.debug('Retrieved %i bytes of %s from %s' % (len(data), contenttype, url))

    return (contenttype, data)

def construct_mail(destination, subject='WebByMail Response', objectlist=[]):
    """
    Returns an email message object addressed to destination, with a
    Subject as specified and a list of tuples from fetch_url
    MIME-enveloped within.
    """
    msg = MIMEMultipart()
    msg['From'] = __SENDER__
    msg['To'] = destination
    msg['Subject'] = subject
    msg.preamble = "This page was retrieved for you by " + __USERAGENT__

    for obj in objectlist:
        logger.debug('Attaching object of type ' + obj[0])
        maintype, subtype = obj[0].split('/', 1)

        if maintype == 'text':
            attachment = MIMEText(obj[1], _subtype=subtype)
        elif maintype == 'image':
            attachment = MIMEImage(obj[1], _subtype=subtype)
        elif maintype == 'audio':
            attachment = MIMEAudio(obj[1], _subtype=subtype)
        else:
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(obj[1])
            encoders.encode_base64(attachment)

        attachment.add_header('Content-Disposition', 'attachment')
        msg.attach(attachment)

    return msg

def send_mail(destination, message):
    """
    Sends the string message to the string destination.
    """
    s = smtplib.SMTP('localhost')
    s.sendmail(__SENDER__, destination, message)
    s.quit()

if __name__ == '__main__':
    destination, urllist = handle_mail_pipe(sys.stdin)
    for url in urllist:
        objectlist = [fetch_url(url)]

    msg = construct_mail(destination, objectlist=objectlist)
    send_mail(destination, msg.as_string())


