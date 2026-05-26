# core/middleware.py

from django.conf import settings
from django.http import HttpResponse


class MaintenanceModeMiddleware:
    """
    Blocks the entire site when MAINTENANCE_MODE=True
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Allow admin access if needed
        allowed_paths = [
            "/admin/",
            "/static/",
            "/media/",
        ]

        if getattr(settings, "MAINTENANCE_MODE", False):

            # Allow selected paths
            if not any(request.path.startswith(path) for path in allowed_paths):

                return HttpResponse(
                    """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Maintenance</title>
                        <style>
                            body{
                                margin:0;
                                padding:0;
                                background:white;
                                display:flex;
                                justify-content:center;
                                align-items:center;
                                height:100vh;
                                font-family:Arial,sans-serif;
                            }
                        </style>
                    </head>
                    <body>
                    </body>
                    </html>
                    """,
                    content_type="text/html",
                    status=503
                )

        response = self.get_response(request)
        return response