import app.main as app_main
from app.login_design import ModernLoginDialog

# Keep the existing application logic and database, but replace only the login UI.
app_main.LoginDialog = ModernLoginDialog


def main():
    return app_main.main()


if __name__ == "__main__":
    main()
