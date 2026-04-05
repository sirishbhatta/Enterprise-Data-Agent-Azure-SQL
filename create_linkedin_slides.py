#!/usr/bin/env python3
"""
Screenshot carousel HTML slides for LinkedIn upload.
Creates individual PNG files for each slide at LinkedIn carousel dimensions.

Run this script on your Windows machine:
    python create_linkedin_slides.py

Requirements:
    pip install playwright
    playwright install chromium
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright


async def screenshot_carousel(html_file_path, output_dir):
    """
    Take screenshots of each slide in the HTML carousel.

    Args:
        html_file_path: Path to the HTML carousel file
        output_dir: Directory to save PNG files
    """

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # LinkedIn carousel optimal dimensions (1080x1350px for best quality)
    viewport_width = 1080
    viewport_height = 1350

    html_path = Path(html_file_path).resolve()
    file_url = html_path.as_uri()

    print(f"📂 Output directory: {output_dir}")
    print(f"🌐 Opening carousel from: {file_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height}
        )

        await page.goto(file_url, wait_until="networkidle")

        # Wait for carousel to load
        try:
            await page.wait_for_selector(".carousel-container", timeout=5000)
        except Exception as e:
            print(f"❌ Error: Could not find carousel. {e}")
            await browser.close()
            return

        # Get the number of slides by checking slide-number elements
        slide_numbers = await page.locator(".slide-number").count()

        if slide_numbers == 0:
            print("❌ No slides found in carousel!")
            await browser.close()
            return

        print(f"✅ Found {slide_numbers} slides\n")

        # Screenshot each slide
        for slide_num in range(1, slide_numbers + 1):
            # Navigate to the slide using arrow keys
            if slide_num == 1:
                # First slide is already active on load
                print(f"📸 Slide {slide_num}/{slide_numbers}...", end=" ", flush=True)
            else:
                # Press right arrow to navigate to next slide
                for _ in range(slide_num - 1):
                    await page.press("body", "ArrowRight")
                    await page.wait_for_timeout(400)  # Wait for slide transition animation

                print(f"📸 Slide {slide_num}/{slide_numbers}...", end=" ", flush=True)

            # Get the carousel container for screenshot
            carousel = page.locator(".carousel-container")

            # Take screenshot
            filename = f"slide_{slide_num:02d}.png"
            filepath = os.path.join(output_dir, filename)

            await carousel.screenshot(path=filepath)
            file_size_kb = os.path.getsize(filepath) / 1024
            print(f"✅ ({file_size_kb:.0f} KB)")

        await browser.close()

        print(f"\n{'='*60}")
        print(f"✅ SUCCESS! All {slide_numbers} slides saved to:")
        print(f"   {output_dir}")
        print(f"{'='*60}")
        print(f"\n📱 Next steps for LinkedIn:")
        print(f"   1. Go to LinkedIn and create a new post")
        print(f"   2. Click on the carousel/slideshow icon")
        print(f"   3. Upload the slide_*.png files in order (01-09)")
        print(f"   4. Add captions and post!")


async def main():
    """Main function."""
    # Update these paths to match your setup
    html_file = r"C:\Users\siris\sirish_ai\LinkedIn_Carousel_RAG_COMPLETE.html"
    output_directory = r"C:\Users\siris\sirish_ai\linkedin_carousel_images"

    # Check if HTML file exists
    if not Path(html_file).exists():
        print(f"❌ Error: HTML file not found at:\n   {html_file}")
        print(f"\nPlease update the html_file path in this script.")
        return

    await screenshot_carousel(html_file, output_directory)


if __name__ == "__main__":
    print("🚀 LinkedIn Carousel Screenshot Generator\n")
    asyncio.run(main())
