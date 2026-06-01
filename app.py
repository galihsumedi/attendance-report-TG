import os

from dotenv import load_dotenv
from flask import Flask, redirect, url_for

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
    app.config['OUTPUT_FOLDER'] = os.environ.get('OUTPUT_FOLDER', 'output')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

    from database import init_db
    init_db(app)

    from routes.auth import bp as auth_bp
    from routes.upload import bp as upload_bp
    from routes.periods import bp as periods_bp
    from routes.review import bp as review_bp
    from routes.export import bp as export_bp
    from routes.employees import bp as employees_bp
    from routes.settings import bp as settings_bp

    for bp in (auth_bp, upload_bp, periods_bp, review_bp, export_bp, employees_bp, settings_bp):
        app.register_blueprint(bp)

    @app.route('/')
    def index():
        return redirect(url_for('upload.upload_page'))

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
