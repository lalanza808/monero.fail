import logging

from flask import Flask

from xmrnodes.routes import meta, api
from xmrnodes import cli, filters


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)
app.config.from_pyfile("config.py")
app.secret_key = app.config["SECRET_KEY"]
app.register_blueprint(meta.bp)
app.register_blueprint(api.bp)
app.register_blueprint(cli.bp)
app.register_blueprint(filters.bp)


if __name__ == "__main__":
    app.run()
