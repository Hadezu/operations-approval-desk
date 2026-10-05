"""Actual session/CSRF/HTTP/PostgreSQL journey. Run against a disposable seeded app."""

import json
import os
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

base = os.environ.get("PROOF_BASE_URL", "http://127.0.0.1:8187")
password = os.environ["DEMO_PASSWORD"]
artifacts = Path("test-results/browser")
artifacts.mkdir(parents=True, exist_ok=True)
for _attempt in range(40):
    try:
        with urlopen(base + "/health/", timeout=2) as response:
            if response.status == 200:
                break
    except OSError:
        time.sleep(1)
else:
    raise RuntimeError("Local application did not become healthy")


def sign_in(browser, username, record=False):
    options = {"viewport": {"width": 1440, "height": 1000}, "reduced_motion": "reduce"}
    if record:
        options.update(
            record_video_dir=str(artifacts),
            record_video_size={"width": 1440, "height": 1000},
        )
    context = browser.new_context(**options)
    page = context.new_page()
    page.goto(base + "/login/")
    page.get_by_label("Username:", exact=True).fill(username)
    page.get_by_label("Password:", exact=True).fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(
        page.get_by_role("heading", name="Make the change. Keep the evidence.")
    ).to_be_visible()
    return context, page


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    contexts = []
    try:
        ac, alice = sign_in(browser, "alice")
        contexts.append(ac)
        title = "Require source references before closing exceptions"
        alice.get_by_text("Create a request · North Operations", exact=True).click()
        alice.get_by_label("Title", exact=True).fill(title)
        alice.get_by_label("Proposed change", exact=True).fill(
            "Synthetic change: require the original source reference before an import exception can be closed."
        )
        alice.get_by_label("Reason", exact=True).fill(
            "Make each closed exception traceable to its source record."
        )
        alice.get_by_role("button", name="Create draft", exact=True).click()
        expect(alice.get_by_role("heading", name=title)).to_be_visible()
        detail_url = alice.url
        alice.get_by_label("Reason for submit", exact=True).fill(
            "The change is bounded and ready for independent review."
        )
        alice.get_by_role("button", name="Submit request", exact=True).click()
        expect(alice.get_by_role("heading", name="No action available")).to_be_visible()
        assert (
            alice.get_by_role("button", name="Approve request", exact=True).count() == 0
        )

        bc, bob = sign_in(browser, "bob", record=True)
        contexts.append(bc)
        errors = []
        bob.on("pageerror", lambda error: errors.append(str(error)))
        bob.screenshot(path=str(artifacts / "queue.png"), full_page=True)
        bob.goto(detail_url)
        cc, carol = sign_in(browser, "carol")
        contexts.append(cc)
        carol.goto(detail_url)  # Deliberately retain the same version before Bob acts.
        bob.get_by_label("Reason for approve", exact=True).fill(
            "Reviewed the exact proposal and agreed the source-reference requirement."
        )
        bob.screenshot(path=str(artifacts / "review.png"), full_page=True)
        bob.wait_for_timeout(
            1200
        )  # Readable recording, not a synchronization technique.
        bob.get_by_role("button", name="Approve request", exact=True).click()
        expect(bob.locator(".badge")).to_have_text("APPROVED")
        expect(bob.locator(".event")).to_have_count(3)
        bob.locator(".event").last.get_by_text(
            "Inspect preserved proposal & fingerprint"
        ).click()
        bob.locator(".history").scroll_into_view_if_needed()
        bob.wait_for_timeout(1200)
        bob.screenshot(path=str(artifacts / "history.png"), full_page=True)

        carol.get_by_label("Reason for reject", exact=True).fill(
            "A concurrent reviewer tries a different decision on the old version."
        )
        with carol.expect_response(
            lambda response: "/commands/" in response.url
        ) as conflict:
            carol.get_by_role("button", name="Reject request", exact=True).click()
        assert conflict.value.status == 409
        expect(carol.get_by_role("alert")).to_have_text("STALE_VERSION")
        carol.screenshot(path=str(artifacts / "stale-decision.png"))
        export = bc.request.get(detail_url + "evidence.json")
        assert export.status == 200
        data = export.json()
        assert data["through_version"] == 3 and data["state"] == "APPROVED"
        assert [event["action"] for event in data["events"]] == [
            "create",
            "submit",
            "approve",
        ]
        assert data["events"][-1]["actor_name"] == "bob"
        (artifacts / "decision-evidence.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

        ec, eve = sign_in(browser, "eve")
        contexts.append(ec)
        assert eve.goto(detail_url).status == 404
        assert ec.request.get(detail_url + "evidence.json").status == 404
        bob.set_viewport_size({"width": 390, "height": 844})
        bob.goto(detail_url)
        expect(bob.locator(".badge")).to_have_text("APPROVED")
        assert bob.evaluate("document.documentElement.scrollWidth <= innerWidth")
        bob.screenshot(path=str(artifacts / "mobile.png"), full_page=True)
        assert not errors
        video = bob.video
        bc.close()
        contexts.remove(bc)
        video.save_as(str(artifacts / "approval-demo.webm"))
        print(
            "PASS: actual login, create, submit, independent approval, stale decision 409, cross-team 404, evidence and mobile."
        )
    finally:
        for context in contexts:
            context.close()
        browser.close()
