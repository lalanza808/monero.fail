from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


class SubmitNode(FlaskForm):
    node_url = StringField('Node URL:', validators=[DataRequired()])
