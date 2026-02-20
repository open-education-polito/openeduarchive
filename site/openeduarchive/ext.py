"""OpenEducationArchive extensions."""

from .mail import init_app as init_mail


class OpenEducationArchive:
    """OpenEducationArchive extension."""

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the extension."""
        init_mail(app)
        app.extensions["openeduarchive"] = self
