import datetime
import json
import re
import sys

#magical nonsense to make python2 work
reload(sys)
sys.setdefaultencoding('UTF8')


from flask import Flask, redirect, url_for, render_template, Response, request, jsonify

app = Flask(__name__, template_folder="templates")

from google.appengine.ext import ndb
from google.appengine.api import urlfetch

from models import Music

@app.route('/robots.txt')
def robots():
    return Response("User-agent:*\nDisallow: /", mimetype="text/plain")

@app.route('/')
def index():
    if request.args.get('musicid'):
        musicid = request.args.get('musicid') or 1
        return redirect(url_for('get', musicid=musicid))
    return render_template('index.html')

@app.route('/<int:musicid>')
def get(musicid):
    if int(musicid) == 0:
        return redirect(url_for('get', musicid=1))
    entry = getitem(musicid)
    if entry:
        entry.update_title()  # called every 2 weeks at most
    # entry might be None, handled in template
    domain = request.url_root.rstrip('/') # doesn't work with traling slash for some reason
    return render_template("get.html", id=musicid, entry=entry, domain=domain,
                                                  shuffle=request.args.get('shuffle', False))


@app.route('/browse')
def browse():
    items_per_page = 50
    page_num = int(request.args.get('page', '1'))
    end_index = items_per_page * page_num + 1
    start_index = end_index - items_per_page
    entries = []
    for n in range(start_index, end_index):
        entry = getitem(n)
        if entry:
            entries.append(entry)
            if not entry.title:
                entry.update_title(force=True)
    return render_template('browse.html', page_num=page_num, first_num=start_index, 
                            entries=entries, page_length=items_per_page)


@app.route('/all')
def all():
    entries = Music.query().order(Music.position)
    for entry in entries:
        if not entry.title:
            entry.update_title(force=True)
    return render_template('browse.html', page_num=1, first_num=1, entries=list(entries), page_length=0)
 

@app.route('/add', methods = ['GET', 'POST'])
def add():
    if request.method == 'POST':
        regex = re.compile("https?://(?:www\.|m\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w\-_]*)")
        url = request.values.get('url', '')
        match = regex.match(url)
        if not match:
            return Response(url + " is not a valid video url", mimetype='text/plain',
                                status=400)
        else:
            link = match.group(1)
            valid = urlfetch.fetch('https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v='
                            '{vid}&format=json'.format(vid=link), validate_certificate=True)
            print(valid.status_code)
            
            if valid.status_code != 200:
                return Response(url + " is not a valid youtube video", mimetype="text/plain",
                                    status=400)
            else:
                ip = request.remote_addr
                time = datetime.datetime.utcnow()
                decoded = valid.content.decode('utf-8')
                m = Music(link=link,
                          date_added=time,
                          title_cache_time=time,
                          added_by=request.values.get('name', ''),
                          ip=ip,
                          position=Music.query().count() + 1,  # not saved yet
                          title=json.loads(decoded).get('title',''))

                data = {'id':Music.query().count(), 'url':url, 'link':url_for('get', musicid=Music.query().count() + 1)}
                m.put()
                return jsonify(data)
    else:
        return render_template('add.html')

@app.route('/renumber')
def renumber():
    music = Music.query().order(Music.date_added)
    for i,m in enumerate(music):
        m.position = i+1
        m.put()
    return Response(status=204)


def getitem(num):
    return Music.query(Music.position==num).get()


@app.route('/api/<int:musicid>')
def api(musicid):
    entry = getitem(musicid)
    if entry:
        import time
        timestamp = int(time.mktime(entry.date_added.timetuple())+entry.date_added.microsecond/1000000.0)
        return jsonify({"id": entry.link, "name": entry.added_by, "time": timestamp,
                             'num': musicid})
    return Response(json.dumps({}), mimetype="application/json", status=404)


@app.route('/api/random')
def api_random():
    return redirect(url_for('api', musicid=random_music_num()))


@app.route('/api/latest')
def api_latest():
    return redirect(url_for('api', musicid=latest_music_num()))


@app.route('/api/num')
def num():
    return Response(Music.objects.count(), mimetype='text/plain')


@app.route('/latest')
def latest():
    return redirect(url_for('get', musicid=latest_music_num()))


def random_music_num():
    """Return a random number from the set of valid music numbers."""
    import random
    return random.randint(1, Music.query().count())


def latest_music_num():
    """Return the number of the latest valid music."""
    return Music.query().count()

@app.route('/random')
def random():
    if request.args.get('shuffle', False):
        return redirect(url_for('get', musicid=random_music_num(), shuffle="true"))
    return redirect(url_for('get', musicid=random_music_num()))
