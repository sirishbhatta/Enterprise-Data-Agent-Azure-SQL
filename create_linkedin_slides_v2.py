#!/usr/bin/env python3
"""
LinkedIn Carousel Screenshot Generator - Version 2
Improved slide extraction with proper navigation and verification.

This version:
- Uses JavaScript to explicitly navigate through slides
- Verifies each slide is different from the previous
- Takes screenshots at mobile-optimized dimensions
- Waits for animations to complete
- Generates high-quality PNG files
"""

import asyncio
import os
import hashlib
from pathlib import Path
from playwright.async_api import async_playwright


async def screenshot_carousel_v2(html_file_path, output_dir):
    """
    Take screenshots of each slide with proper navigation verification.
    """

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # LinkedIn carousel: 1080×1350 (4:5 aspect ratio - optimal for mobile)
    # This is wider than a phone but works great for LinkedIn desktop preview
    viewport_width = 1080
    viewport_height = 1350

    html_path = Path(html_file_path).resolve()
    file_url = html_path.as_uri()

    print(f"📂 Output directory: {output_dir}")
    print(f"📱 Viewport: {viewport_width}×{viewport_height} (mobile-optimized)")
    print(f"🌐 Opening: {file_url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Use mobile viewport for better rendering
        page = await browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height},
            device_scale_factor=2  # Retina quality for better text
        )

        await page.goto(file_url, wait_until="networkidle")
        await page.wait_for_selector(".carousel-container", timeout=5000)

        # Get total slides using JavaScript
        total_slides = await page.evaluate("document.querySelectorAll('.slide').length")

        print(f"✅ Found {total_slides} slides\n")

        # Get the slide elements
        slide_count = await page.evaluate("""() => {
            const slideNumbers = document.querySelectorAll('.slide-number');
            return slideNumbers.length;
        }""")

        if slide_count == 0:
            print("❌ Could not find slides!")
            await browser.close()
            return

        print(f"📊 Slide indicators found: {slide_count}\n")

        prev_screenshot_hash = None
        successful_slides = 0

        for slide_num in range(slide_count):
            # Navigate to slide using the carousel's own showSlide function
            await page.evaluate(f"""() => {{
                window.currentSlide = {slide_num};
                if (typeof showSlide === 'function') {{
                    showSlide({slide_num});
                }} else {{
                    // Fallback if showSlide is not available
                    const slides = document.querySelectorAll('.slide');
                    slides.forEach((slide, idx) => {{
                        slide.classList.toggle('active', idx === {slide_num});
                    }});
                }}
            }}""")

            # Wait for animation to complete (increased timeout for safety)
            await page.wait_for_timeout(800)

            # Verify we're on the right slide
            current_slide = await page.evaluate("window.currentSlide")
            active_slides = await page.evaluate("document.querySelectorAll('.slide.active').length")

            if active_slides != 1:
                print(f"⚠️  Slide {slide_num + 1}: Warning - {active_slides} active slides")

            # Get slide title/header for verification
            slide_header = await page.evaluate(f"""() => {{
                const slide = document.querySelectorAll('.slide')[{slide_num}];
                const h1 = slide.querySelector('h1');
                const h2 = slide.querySelector('h2');
                const title = h1 ? h1.textContent : (h2 ? h2.textContent : 'Unknown');
                return title.substring(0, 50);
            }}""")

            print(f"📸 Slide {slide_num + 1}/{slide_count}: {slide_header}...", end=" ", flush=True)

            # Take screenshot
            carousel = page.locator(".carousel-container")
            filename = f"slide_{slide_num + 1:02d}.png"
            filepath = os.path.join(output_dir, filename)

            await carousel.screenshot(path=filepath, type="png")

            # Get file info
            file_size_kb = os.path.getsize(filepath) / 1024

            # Verify file was created and is different from previous
            with open(filepath, 'rb') as f:
                screenshot_hash = hashlib.md5(f.read()).hexdigest()

            if screenshot_hash == prev_screenshot_hash:
                print(f"⚠️  (DUPLICATE CONTENT?)")
            else:
                print(f"✅ ({file_size_kb:.0f} KB)")
                successful_slides += 1

            prev_screenshot_hash = screenshot_hash

        await browser.close()

        print(f"\n{'='*65}")
        if successful_slides == slide_count:
            print(f"✅ SUCCESS! All {slide_count} unique slides saved!")
        else:
            print(f"⚠️  {successful_slides}/{slide_count} slides created")
            print(f"    (Some slides may have identical content)")
        print(f"{'='*65}")
        print(f"\n📁 Files saved to:")
        print(f"   {output_dir}\n")

        print(f"📋 Files created:")
        for i in range(1, slide_count + 1):
            fname = f"slide_{i:02d}.png"
            fpath = os.path.join(output_dir, fname)
            if os.path.exists(fpath):
                size_kb = os.path.getsize(fpath) / 1024
                print(f"   ✓ {fname:20s} ({size_kb:6.0f} KB)")

        print(f"\n📱 Mobile Optimization:")
        print(f"   • Viewport: {viewport_width}×{viewport_height}px (mobile-optimized)")
        print(f"   • Device Pixel Ratio: 2x (Retina quality)")
        print(f"   • Aspect Ratio: 4:5 (perfect for LinkedIn carousel)")
        print(f"\n🚀 Ready for LinkedIn!")
        print(f"   Upload slide_01.png through slide_{slide_count:02d}.png in order")


async def main():
    """Main function."""
    html_file = r"C:\Users\siris\sirish_ai\LinkedIn_Carousel_RAG_COMPLETE.html"
    output_directory = r"C:\Users\siris\sirish_ai\linkedin_carousel_images"

    if not Path(html_file).exists():
        print(f"❌ Error: HTML file not found at:\n   {html_file}")
        return

    await screenshot_carousel_v2(html_file, output_directory)


if __name__ == "__main__":
    print("🚀 LinkedIn Carousel Screenshot Generator v2\n")
    asyncio.run(main())
