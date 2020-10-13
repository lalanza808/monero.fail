import json
import requests
import re
from os import makedirs
from flask import Flask, request, redirect
from flask import render_template, flash, url_for
from urllib.parse import urlparse
from xmrnodes.models import Node


app = Flask(__name__)
app.config.from_envvar("FLASK_SECRETS")
app.secret_key = app.config["SECRET_KEY"]

@app.route("/", methods=["GET", "POST"])
def index():
    itp = 20
    page = request.args.get("page", 1)
    try:
        page = int(page)
    except:
        flash("Wow, wtf hackerman. Cool it.")
        page = 1

    nodes = Node.select().where(Node.available==True).order_by(Node.datetime_entered.desc()).paginate(page, itp)
    total_pages = Node.select().count() / itp
    return render_template("index.html", nodes=nodes, page=page, total_pages=total_pages)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        url = request.form.get("url")
        regex = re.compile(
                r'^(?:http)s?://' # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                r'localhost|' #localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                r'(?::\d+)?' # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        re_match = re.match(regex, url)

        if re_match is not None:
            _url = urlparse(url)
            try:
                endpoint = f"{_url.scheme}://{_url.netloc}"
                r = requests.get(endpoint + "/get_info", timeout=3)
                r.raise_for_status()
                # print(r.json())
                return {"status": "success"}
            except requests.exceptions.ConnectTimeout:
                flash("connection timed out. double-check the port")
                return {"status": "fail", "reason": "timeout"}
            except requests.exceptions.SSLError:
                flash("invalid certificate")
                return {"status": "fail", "reason": "invalid cert"}
            except Exception as e:
                flash("failed to send req", str(e))
                print(e)
                return {"status": "fail"}
        else:
            flash("invalid url provided")
            return {"status": "fail"}

        return "ok"
        node = Node(
            scheme=proto,
            address=addr,
            port=port,
            version=r.json()["version"],
            tor=addr.endswith(".onion"),
            available=r.json()["status"] == "OK",
            mainnet=r.json()["mainnet"],
        )
        node.save()
        return {"status": "success"}
    return redirect("/")


@app.route("/about")
def about():
    return render_template("about.html")

@app.errorhandler(404)
def not_found(error):
    flash("nothing there, brah")
    return redirect("/")

if __name__ == "__main__":
    app.run()
