from flask import Blueprint, render_template

bp = Blueprint("page", __name__)


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/cara-kerja")
def how():
    return render_template("how.html")


@bp.route("/edukasi")
def education():
    return render_template("education.html")


@bp.route("/tentang")
def about():
    return render_template("about.html")
