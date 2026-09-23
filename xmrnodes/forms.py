from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


class SubmitNode(FlaskForm):
    node_url = StringField(
        "",
        validators=[DataRequired()],
        render_kw={"placeholder": "Node URL - proto://hostname:port (http://hostname:18081, http://ipv4:18081, http://[ipv6]:18081)"},
    )


class SubmitLWS(FlaskForm):
    lws_url = StringField(
        "LWS URL",
        validators=[DataRequired()],
        render_kw={"placeholder": "LWS URL - https://hostname:port (https://lws.example.com)"},
    )
    contact = StringField(
        "Contact",
        validators=[DataRequired()],
        render_kw={"placeholder": "Contact info (email, Matrix, etc.)"},
    )
    details_url = StringField(
        "Details URL",
        validators=[DataRequired()],
        render_kw={"placeholder": "Details page URL (GitHub repo, website, etc.)"},
    )
