"""
Réveille l'application Streamlit Community Cloud si elle s'est mise en veille.

Une simple requête HTTP ne suffit pas : la page de veille demande de cliquer
sur « Yes, get this app back up! ». Ce script ouvre l'application dans un vrai
navigateur, clique sur ce bouton s'il est présent, puis attend le démarrage.

Usage :  python .github/scripts/reveil_app.py https://<mon-app>.streamlit.app
"""

import sys

from playwright.sync_api import sync_playwright

WAKE_BUTTON = "Yes, get this app back up"


def main(url: str) -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(10_000)

        button = page.get_by_role("button", name=WAKE_BUTTON)
        if button.count():
            print("Application en veille : réveil en cours…")
            button.first.click()
            page.wait_for_timeout(5_000)
        else:
            print("Application déjà active.")

        # L'application est prête quand Streamlit a affiché son contenu, dans
        # la page ou dans un iframe (cas de *.streamlit.app).
        try:
            for _ in range(48):  # jusqu'à 4 minutes
                if any(f.locator('[data-testid="stApp"]').count() for f in page.frames):
                    print("Application prête.")
                    return 0
                page.wait_for_timeout(5_000)
            print("L'application ne répond pas après 4 minutes : vérifier sur share.streamlit.io.")
            return 1
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
