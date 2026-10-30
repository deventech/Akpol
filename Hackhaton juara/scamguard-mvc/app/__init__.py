from flask import Flask


def create_app():
    app = Flask(
        __name__,
        template_folder="views/templates",
        static_folder="views/static",
    )
    app.config.from_object("app.config.Config")

    from app.controllers.page_controller import bp as page_bp
    from app.controllers.check_controller import bp as check_bp

    app.register_blueprint(page_bp)
    app.register_blueprint(check_bp)
    return app
