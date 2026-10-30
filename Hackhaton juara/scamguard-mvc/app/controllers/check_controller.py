from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from app.models.risk_scorer import build_result
from app.models.url_analyzer import analyze_url

bp = Blueprint("check", __name__)


@bp.route("/check", methods=["GET", "POST"])
def check():
    if request.method == "GET":
        return render_template("check.html")
    raw = request.form.get("url", "")
    analysis = analyze_url(raw)
    if "error" in analysis:
        return render_template("check.html", error=analysis["error"], url=raw), 400
    result = build_result(analysis)
    result["checked_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    return render_template("result.html", r=result)


@bp.post("/api/check")
def api_check():
    analysis = analyze_url((request.get_json(silent=True) or {}).get("url", ""))
    if "error" in analysis:
        return jsonify(error=analysis["error"]), 400
    return jsonify(build_result(analysis))
