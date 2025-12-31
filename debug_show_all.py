"""Debug script to test different selectors for 'Show all' button."""

import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_show_all_selectors():
    """Test different selector strategies for the 'Show all' button."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to SofaScore football page
        url = "https://www.sofascore.com/football"
        logger.info(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle")

        # Wait a bit for page to settle
        await asyncio.sleep(3)

        # Test different selectors
        selectors = [
            # Original approach
            ("get_by_role with exact name", lambda: page.get_by_role("button", name="Show all")),

            # Partial text match
            ("get_by_text", lambda: page.get_by_text("Show all")),
            ("get_by_text with exact=False", lambda: page.get_by_text("Show all", exact=False)),

            # CSS selectors
            ("CSS has-text", lambda: page.locator("button:has-text('Show all')")),
            ("CSS class selector", lambda: page.locator("button.button--variant_clear:has-text('Show all')")),

            # XPath
            ("XPath contains", lambda: page.locator("xpath=//button[contains(text(), 'Show all')]")),
        ]

        logger.info("\n" + "="*60)
        logger.info("Testing different selectors...")
        logger.info("="*60)

        for name, selector_fn in selectors:
            try:
                locator = selector_fn()
                count = await locator.count()
                logger.info(f"\n{name}:")
                logger.info(f"  Found: {count} button(s)")

                if count > 0:
                    # Check first button
                    first_button = locator.first
                    is_visible = await first_button.is_visible()
                    text = await first_button.text_content()
                    logger.info(f"  First button visible: {is_visible}")
                    logger.info(f"  First button text: {repr(text)}")

                    # Get accessible name
                    try:
                        accessible_name = await first_button.get_attribute("aria-label")
                        logger.info(f"  Accessible name: {repr(accessible_name)}")
                    except:
                        logger.info(f"  Accessible name: None")

            except Exception as e:
                logger.error(f"{name} - Error: {e}")

        logger.info("\n" + "="*60)
        logger.info("Attempting to click with different methods...")
        logger.info("="*60)

        # Try clicking with the most promising selector
        try:
            # Wait for user to see the page
            logger.info("\nWaiting 5 seconds before attempting clicks...")
            await asyncio.sleep(5)

            # Try CSS selector approach
            buttons = page.locator("button:has-text('Show all')")
            count = await buttons.count()
            logger.info(f"\nFound {count} 'Show all' buttons with CSS selector")

            clicked = 0
            for i in range(count):
                button = buttons.nth(i)
                if await button.is_visible():
                    logger.info(f"Clicking button {i+1}...")
                    await button.scroll_into_view_if_needed()
                    await button.click()
                    clicked += 1
                    await asyncio.sleep(1)
                    logger.info(f"  ✓ Clicked successfully")
                else:
                    logger.info(f"Button {i+1} not visible, skipping")

            logger.info(f"\nTotal clicked: {clicked}")

            # Keep browser open to see results
            logger.info("\nKeeping browser open for 10 seconds to view results...")
            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"Click attempt failed: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_show_all_selectors())
