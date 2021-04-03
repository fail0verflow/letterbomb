import os, zipfile, hashlib, hmac, struct, logging, random, json
import urllib
from io import BytesIO
from logging.handlers import SMTPHandler
from datetime import datetime, timedelta
from flask import Flask, request, g, render_template, make_response, redirect, url_for

app = Flask(__name__)
app.config.from_object("config")

TEMPLATES = {
    'U':"templateU.bin",
    'E':"templateE.bin",
    'J':"templateJ.bin",
    'K':"templateK.bin",
}

BUNDLEBASE = os.path.join(app.root_path, 'bundle')
COUNTRY_REGIONS = dict([l.split(" ") for l in open(os.path.join(app.root_path, 'country_regions.txt')).read().split("\n") if l])

try:
    import geoip2.database, geoip2.errors
    gi = geoip2.database.Reader('/usr/share/GeoIP/GeoLite2-Country.mmdb')
except ImportError:
    gi = None

class RequestFormatter(logging.Formatter):
    def format(self, record):
        s = logging.Formatter.format(self, record)
        try:
            return '[%s] [%s] [%s %s] '%(self.formatTime(record), request.remote_addr, request.method, request.path) + s
        except:
            return '[%s] [SYS] '%self.formatTime(record) + s

if not app.debug:
    mail_handler = SMTPHandler(app.config['SMTP_SERVER'],
                                app.config['APP_EMAIL'],
                                app.config['ADMIN_EMAIL'], 'LetterBomb ERROR')
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

    handler = logging.FileHandler(os.path.join(app.root_path, 'log', 'info.log'))
    handler.setLevel(logging.INFO)
    handler.setFormatter(RequestFormatter())
    app.logger.addHandler(handler)

    app.logger.setLevel(logging.INFO)
    app.logger.warning('Starting...')

def region():
    if gi is None:
        return 'E'
    try:
        country = gi.country(request.remote_addr).country.iso_code
        app.logger.info("GI: %s -> %s", request.remote_addr, country)
        return COUNTRY_REGIONS.get(country, 'E')
    except geoip2.errors.AddressNotFoundError:
        return 'E'
    except:
        app.logger.exception("GeoIP exception")
        return 'E'

def _index(error=None):
    g.recaptcha_args = 'k=%s' % app.config['RECAPTCHA_PUBLICKEY']
    rs = make_response(render_template('index.html', region=region(), error=error))
    #rs.headers['Cache-Control'] = 'private, max-age=0, no-store, no-cache, must-revalidate'
    #rs.headers['Etag'] = str(random.randrange(2**64))
    rs.headers['Expires'] = 'Thu, 01 Dec 1983 20:00:00 GMT'
    return rs


@app.route('/')
def index():
    return _index()


def captcha_check():
    try:
        oform = {
            #"privatekey": app.config['RECAPTCHA_PRIVATEKEY'],
            "secret": app.config['RECAPTCHA_PRIVATEKEY'],
            "remoteip": request.remote_addr,
            #"challenge": request.form.get('recaptcha_challenge_field',['']),
            #"response": request.form.get('recaptcha_response_field',[''])
            "response": request.form.get('g-recaptcha-response',[''])
        }
        #f = urllib.urlopen("http://api-verify.recaptcha.net/verify", urllib.urlencode(oform))
        f = urllib.request.urlopen("https://www.google.com/recaptcha/api/siteverify", urllib.parse.urlencode(oform).encode("utf-8"))

        #result = f.readline().replace("\n","")
        #error = f.readline().replace("\n","")
        d = json.load(f)
        result = d["success"]
        f.close()

        if not result:#  != 'true':
            #if error != 'incorrect-captcha-sol':
            app.logger.info("ReCaptcha fail: %r, %r", oform, d)
            #g.recaptcha_args += "&error=" + error
            return False

    except:
        #g.recaptcha_args += "&error=unknown"
        return False
    return True

@app.route('/haxx', methods=["POST"])
def haxx():
    OUI_LIST = [bytes.fromhex(i) for i in open(os.path.join(app.root_path, 'oui_list.txt')).read().split("\n") if len(i) == 6]
    g.recaptcha_args = 'k=%s' % app.config['RECAPTCHA_PUBLICKEY']
    dt = datetime.utcnow() - timedelta(1)
    delta = (dt - datetime(2000, 1, 1))
    timestamp = delta.days * 86400 + delta.seconds
    try:
        mac = bytes((int(request.form[i],16)) for i in "abcdef")
        template = TEMPLATES[request.form['region']]
        bundle = 'bundle' in request.form
    except:
        return _index("Invalid input.")
    if not captcha_check():
        return _index("Are you a human?")

    if mac == b"\x00\x17\xab\x99\x99\x99":
        app.logger.info('Derp MAC %s at %d ver %s bundle %r', mac.hex(), timestamp, request.form['region'], bundle)
        return _index("If you're using Dolphin, try File->Open instead ;-).")

    if not any([mac.startswith(i) for i in OUI_LIST]):
        app.logger.info('Bad MAC %s at %d ver %s bundle %r', mac.hex(), timestamp, request.form['region'], bundle)
        return _index("The exploit will only work if you enter your Wii's MAC address.")


    key = hashlib.sha1(mac + b"\x75\x79\x79").digest()
    blob = bytearray(open(os.path.join(app.root_path, template), 'rb').read())
    blob[0x08:0x10] = key[:8]
    blob[0xb0:0xc4] = bytes(20)
    blob[0x7c:0x80] = struct.pack(">I", timestamp)
    blob[0x80:0x8a] = (b"%010d" % timestamp)
    blob[0xb0:0xc4] = hmac.new(key[8:], bytes(blob), hashlib.sha1).digest()

    path = "private/wii/title/HAEA/%s/%s/%04d/%02d/%02d/%02d/%02d/HABA_#1/txt/%08X.000" % (
        key[:4].hex().upper(), key[4:8].hex().upper(),
        dt.year, dt.month-1, dt.day, dt.hour, dt.minute, timestamp
    )

    zipdata = BytesIO()
    zip = zipfile.ZipFile(zipdata, 'w')
    zip.writestr(path, blob)
    BUNDLE = [(name, os.path.join(BUNDLEBASE,name)) for name in os.listdir(BUNDLEBASE) if not name.startswith(".")]
    if bundle:
        for name, path in BUNDLE:
            zip.write(path, name)
    zip.close()

    app.logger.info('LetterBombed %s at %d ver %s bundle %r', mac.hex(), timestamp, request.form['region'], bundle)

    rs = make_response(zipdata.getvalue())
    zipdata.close()
    rs.headers.add('Content-Disposition', 'attachment', filename="LetterBomb.zip")
    rs.headers['Content-Type'] = 'application/zip'
    return rs

application=app

if __name__ == "__main__":
    app.run('0.0.0.0', 10142)
