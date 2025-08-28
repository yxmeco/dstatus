from app import create_app, db
from app.models.domain import Domain
from app.models.certificate import Certificate
from app.models.notification import URLCheck, Notification

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'Domain': Domain,
        'Certificate': Certificate,
        'URLCheck': URLCheck,
        'Notification': Notification
    }

if __name__ == '__main__':
    app.run(debug=True)
