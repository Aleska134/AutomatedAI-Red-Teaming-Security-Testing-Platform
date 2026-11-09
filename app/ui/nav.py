"""Registry of the dashboard pages, filled by ``frontend.py`` at start-up.

Lets one page link to another (``st.page_link``) without importing it.
"""

pages: dict = {}
