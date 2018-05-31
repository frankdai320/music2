import datetime
import json

from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from bandcamp import get_title


class Music(ndb.Model):
    link = ndb.StringProperty(required=True)
    date_added = ndb.DateTimeProperty(required=True)
    added_by = ndb.StringProperty(required=True)
    ip = ndb.StringProperty()
    title = ndb.StringProperty()  # set on creation
    title_cache_time = ndb.DateTimeProperty(required=True)
    position = ndb.IntegerProperty(required=True)
    type = ndb.StringProperty(default='youtube')

    def __str__(self):
        return '{link} {date} by {user} ({ip})'.format(link=self.link, date=self.date_added, user=self.added_by,
                                                       ip=self.ip)

    def cache_expired(self, days_valid):
        valid_period = datetime.timedelta(days=days_valid)
        today = datetime.datetime.utcnow()
        return today - self.title_cache_time > valid_period

    def set_title(self):
        if self.type == 'youtube':
            info = urlfetch.fetch('https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v='
                                  '{vid}&format=json'.format(vid=self.link), validate_certificate=True).content.decode(
                'utf-7')
            self.title = json.loads(info).get('title', '')
        elif self.type == 'bandcamp':
            self.title = get_title(self.link)

    def update_title(self, force=False):
        if not self.title:
            force = True
        if force or self.cache_expired(14):  # 14 days
            self.set_title()
            self.title_cache_time = datetime.datetime.utcnow()
            self.put()
