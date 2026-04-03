"""
app.py — Flask web server for the NFL Stats Quiz Game.
"""

import os
import secrets
from flask import Flask, render_template, request, session, jsonify, redirect, url_for as flask_url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from data_loader import load_data
from quiz_engine import generate_questions, format_stat_value


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    root = os.environ.get("APPLICATION_ROOT", "/").strip() or "/"
    if root != "/":
        app.config["APPLICATION_ROOT"] = root
        app.config["SESSION_COOKIE_PATH"] = root

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )

    app_root = (os.environ.get("APPLICATION_ROOT") or "").strip().rstrip("/") or ""

    def prefixed_url_for(endpoint, **values):
        """Prefix routes with APPLICATION_ROOT when reverse-proxy headers omit script root."""
        path = flask_url_for(endpoint, **values)
        if not app_root:
            return path
        if path in ("/", ""):
            return f"{app_root}/"
        if path.startswith(f"{app_root}/") or path == app_root:
            return path
        if path.startswith("/"):
            return f"{app_root}{path}"
        return path

    @app.context_processor
    def inject_prefixed_url_for():
        return dict(url_for=prefixed_url_for, nfl_quiz_app_root=app_root)

    # Load player data at startup
    player_data_cache = None

    def get_player_data():
        nonlocal player_data_cache
        if player_data_cache is None:
            player_data_cache = load_data()
        return player_data_cache

    @app.route("/")
    def index():
        """Landing page — choose quiz length."""
        return render_template("index.html")

    @app.route("/quiz/start", methods=["POST"])
    def quiz_start():
        """Generate questions and start a new quiz."""
        num_questions = int(request.form.get("num_questions", 10))
        if num_questions not in (10, 15, 25):
            num_questions = 10

        player_data = get_player_data()
        questions = generate_questions(num_questions, player_data)

        # Store questions in session
        session["questions"] = questions
        session["current"] = 0
        session["score"] = 0
        session["total"] = len(questions)
        session["answers"] = []

        return redirect(prefixed_url_for("quiz"))

    @app.route("/quiz")
    def quiz():
        """Render the quiz page."""
        if "questions" not in session:
            return redirect(prefixed_url_for("index"))
        return render_template(
            "quiz.html",
            total=session["total"],
        )

    @app.route("/api/question/<int:n>")
    def api_question(n):
        """Return question n as JSON (without the answer)."""
        questions = session.get("questions", [])
        if n < 0 or n >= len(questions):
            return jsonify({"error": "Invalid question number"}), 400

        q = questions[n]
        return jsonify({
            "question_number": n,
            "total": session.get("total", 0),
            "player1": q["player1"],
            "player2": q["player2"],
            "stat_display": q["stat_display"],
            "question_word": q["question_word"],
            "season": q["season"],
        })

    @app.route("/api/answer/<int:n>", methods=["POST"])
    def api_answer(n):
        """Check the user's answer for question n."""
        questions = session.get("questions", [])
        if n < 0 or n >= len(questions):
            return jsonify({"error": "Invalid question number"}), 400

        data = request.get_json()
        user_answer = data.get("answer")

        q = questions[n]
        correct = q["correct_answer"]
        is_correct = (user_answer == correct)

        if is_correct:
            session["score"] = session.get("score", 0) + 1

        # Track answer
        answers = session.get("answers", [])
        answers.append({
            "question": n,
            "user_answer": user_answer,
            "correct_answer": correct,
            "is_correct": is_correct,
        })
        session["answers"] = answers
        session.modified = True

        return jsonify({
            "is_correct": is_correct,
            "correct_answer": correct,
            "player1_value": format_stat_value(q["stat_name"], q["player1_value"]),
            "player2_value": format_stat_value(q["stat_name"], q["player2_value"]),
            "stat_display": q["stat_display"],
            "score": session.get("score", 0),
        })

    @app.route("/results")
    def results():
        """Show final results."""
        if "questions" not in session:
            return redirect(prefixed_url_for("index"))

        score = session.get("score", 0)
        total = session.get("total", 0)
        percentage = round((score / total) * 100) if total > 0 else 0

        # Letter grade
        if percentage >= 90:
            grade = "A"
        elif percentage >= 80:
            grade = "B"
        elif percentage >= 70:
            grade = "C"
        elif percentage >= 60:
            grade = "D"
        else:
            grade = "F"

        return render_template(
            "results.html",
            score=score,
            total=total,
            percentage=percentage,
            grade=grade,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
