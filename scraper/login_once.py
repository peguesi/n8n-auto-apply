from playwright.sync_api import sync_playwright

if __name__ == "__main__":
    with sync_playwright() as p:
        browser_type = p.webkit
        user_data_dir = "/Users/zeh/.pw-session"

        context = browser_type.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.linkedin.com/login")
        input("🟢 Log in manually, then press ENTER to save session and exit...")
        context.close()
        