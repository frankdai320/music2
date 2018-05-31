import datetime
import json
import re
import sys

from bandcamp import get_raw_link, get_title

# magical nonsense to make python2 work
reload(sys)
sys.setdefaultencoding('UTF8')

from flask import Flask, redirect, url_for, render_template, Response, request, jsonify

app = Flask(__name__, template_folder="templates")

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


@app.route('/<int:musicid>/')
def get(musicid):
    if int(musicid) == 0:
        return redirect(url_for('get', musicid=1))
    entry = getitem(musicid)
    if entry:
        entry.update_title()  # called every 2 weeks at most
    # entry might be None, handled in template
    domain = request.url_root.rstrip('/')  # doesn't work with traling slash for some reason
    return render_template("get.html", id=musicid, entry=entry, domain=domain,
                           shuffle=request.args.get('shuffle', False))


@app.route('/all/')
def all():
    entries = Music.query().order(Music.position)
    for entry in entries:
        if not entry.title:
            entry.update_title(force=True)
    return render_template('all.html', entries=list(entries))


@app.route('/add/', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        yt_regex = re.compile("https?://(?:www\.|m\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w\-_]*)")
        url = request.values.get('url', '')
        yt_match = yt_regex.match(url)
        bc_match = None
        if not yt_match:
            bc_match = get_raw_link(url)

        if not (yt_match or bc_match):
            return Response(url + " is not a valid url", mimetype='text/plain', status=400)
        else:
            if yt_match:
                link = yt_match.group(1)
                valid = urlfetch.fetch('https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v='
                                       '{vid}&format=json'.format(vid=link), validate_certificate=True)

                if valid.status_code != 200:
                    return Response(url + " is not a valid youtube video", mimetype="text/plain",
                                    status=400)

                decoded = valid.content.decode('utf-8')
                title = json.loads(decoded).get('title', '')
            else:
                link = url
                title = get_title(url)

            ip = request.remote_addr
            time = datetime.datetime.utcnow()

            m = Music(link=link,
                      date_added=time,
                      title_cache_time=time,
                      added_by=request.values.get('name', ''),
                      ip=ip,
                      position=Music.query().count() + 1,  # not saved yet
                      title=title,
                      type='youtube' if yt_match else 'bandcamp')

            data = {'id': Music.query().count(), 'url': url,
                    'link': url_for('get', musicid=Music.query().count() + 1),
                    'type': m.type}
            m.put()
            return jsonify(data)
    else:
        return render_template('add.html')


@app.route('/renumber/')
def renumber():
    music = Music.query().order(Music.date_added)
    for i, m in enumerate(music):
        m.position = i + 1
        m.put()
    return Response(status=204)


def getitem(num):
    return Music.query(Music.position == num).get()


@app.route('/api/<int:musicid>/')
def api(musicid):
    entry = getitem(musicid)
    if entry:
        import time
        timestamp = int(time.mktime(entry.date_added.timetuple()) + entry.date_added.microsecond / 1000000.0)
        return jsonify({"id": entry.link, "name": entry.added_by, "time": timestamp,
                        'num': musicid, 'type': entry.type})
    return Response(json.dumps({}), mimetype="application/json", status=404)


@app.route('/api/random/')
def api_random():
    return redirect(url_for('api', musicid=random_music_num()))


@app.route('/api/latest/')
def api_latest():
    return redirect(url_for('api', musicid=latest_music_num()))


@app.route('/api/num/')
def num():
    return Response(Music.objects.count(), mimetype='text/plain')


@app.route('/latest/')
def latest():
    return redirect(url_for('get', musicid=latest_music_num()))


def random_music_num():
    """Return a random number from the set of valid music numbers."""
    import random
    return random.randint(1, Music.query().count())


def latest_music_num():
    """Return the number of the latest valid music."""
    return Music.query().count()


@app.route('/random/')
def random():
    if request.args.get('shuffle', False):
        return redirect(url_for('get', musicid=random_music_num(), shuffle="true"))
    return redirect(url_for('get', musicid=random_music_num()))


@app.route('/bandcamp/')
def bandcamp():
    link = request.args.get('link')
    if not link:
        return '', 400
    raw_link = get_raw_link(link)
    title = request.args.get('title') or get_title(link)  # get_title() makes a network call
    if not raw_link:
        return '', 400
    return render_template('bandcamp_iframe.html', raw_link=raw_link, title=title, link=link)
