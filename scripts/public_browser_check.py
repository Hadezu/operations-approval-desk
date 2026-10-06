"""Real HTTP/PostgreSQL guided journeys; never runs against a production URL."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

root = Path(__file__).resolve().parents[1]
artifacts = root / "test-results/public-browser"
artifacts.mkdir(parents=True, exist_ok=True)
port = int(os.environ.get("DEMO_TEST_PORT", "8189"))
base = f"http://127.0.0.1:{port}"
env = {
    **os.environ,
    "PUBLIC_DEMO": "1",
    "PORT": str(port),
    "BIND_HOST": "127.0.0.1",
    "HTTPS_ONLY": "0",
    "TRUST_HTTPS_PROXY": "0",
}
results = []
with (artifacts / "server.log").open("w", encoding="utf-8") as log:
    server = subprocess.Popen(
        [sys.executable, "-m", "scripts.serve"],
        cwd=root,
        env=env,
        stdout=log,
        stderr=log,
    )
    try:
        for _ in range(40):
            if server.poll() is not None:
                raise RuntimeError("Public demo server exited; inspect server.log")
            try:
                with urlopen(base + "/health/", timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Local public server did not become healthy")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for locale in ("en", "pl"):
                for width in (1440, 390):
                    ctx = browser.new_context(
                        viewport={"width": width, "height": 960},
                        record_video_dir=str(artifacts),
                        record_video_size={"width": width, "height": 960},
                    )
                    page = ctx.new_page()
                    errors = []
                    page.on(
                        "pageerror", lambda error, sink=errors: sink.append(str(error))
                    )
                    response = page.goto(f"{base}/demo/{locale}/")
                    assert response.status == 200
                    assert page.locator("html").get_attribute("lang") == locale
                    page.locator('form[action$="/start/"] button').click()
                    expect(page.locator(".workspace")).to_be_visible()
                    page.screenshot(
                        path=str(artifacts / f"{locale}-{width}-draft.png"),
                        full_page=True,
                    )
                    page.locator("form.action").filter(
                        has=page.locator('input[value="submit"]')
                    ).get_by_role("button").click()
                    page.locator('button[value="reviewer"]').click()
                    page.locator("form.action").filter(
                        has=page.locator('input[value="approve"]')
                    ).get_by_role("button").click()
                    expect(page.locator(".notice")).to_be_visible()
                    with page.expect_download() as download:
                        page.locator(".download").click()
                    path = artifacts / f"{locale}-{width}-evidence.json"
                    download.value.save_as(path)
                    report = json.loads(path.read_text(encoding="utf-8"))
                    assert report["state"] == "APPROVED" and len(report["events"]) == 3
                    page.locator('button[value="second_reviewer"]').click()
                    page.locator(".experiment summary").click()
                    page.locator(".experiment button").click()
                    expect(
                        page.get_by_text("STALE_VERSION", exact=True)
                    ).to_be_visible()
                    page.screenshot(
                        path=str(artifacts / f"{locale}-{width}-conflict.png"),
                        full_page=True,
                    )
                    page.locator("main a").click()
                    page.locator('button[value="auditor"]').click()
                    assert page.locator("form.action").count() == 0
                    assert page.locator(".events li").count() == 3
                    assert not page.evaluate(
                        "document.documentElement.scrollWidth > innerWidth"
                    )
                    page.screenshot(
                        path=str(artifacts / f"{locale}-{width}-approved.png"),
                        full_page=True,
                    )
                    href = page.locator('footer a[href*="example="]').get_attribute(
                        "href"
                    )
                    assert "example=services%2Finternal-applications#contact" in href
                    assert not errors, errors
                    video = page.video
                    ctx.close()
                    video.save_as(str(artifacts / f"tour-{locale}-{width}.webm"))
                    results.append(
                        {
                            "locale": locale,
                            "width": width,
                            "decision": "APPROVED",
                            "events": 3,
                            "stale": "409 / STALE_VERSION",
                            "auditor": "read-only",
                            "overflow": False,
                            "page_errors": errors,
                        }
                    )
            browser.close()
        (artifacts / "results.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(json.dumps(results, indent=2))
    finally:
        server.terminate()
        server.wait(timeout=10)
