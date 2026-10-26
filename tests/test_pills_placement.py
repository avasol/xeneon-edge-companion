"""THE PILLS, FELT — the buttons sit UNDER the reply they belong to (aedelgard-body
docs/SPEC_pills_felt.md F2). Found live: on a 2560x720 Edge, the pills rendered as a
third flex column to the RIGHT of the bubble, at its TOP; on a long reply that top was
scrolled out of view, so the owner never saw them."""
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
LONG = "\n\n".join(f"Paragraph {i}: the restart worked and all checks pass." for i in range(14))
TEXT = LONG + "\n\nYour move: say go.\n\n[[options: go | hold]]"


@pytest.fixture(scope="module")
def page():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-sandbox"])
        except Exception as e:  # no browser in this sandbox
            pytest.skip(f"chromium unavailable: {e}")
        pg = b.new_page(viewport={"width": 2560, "height": 720})
        pg.goto((ROOT / "index.html").as_uri())
        pg.wait_for_timeout(500)
        yield pg
        b.close()


def _geom(page):
    page.evaluate("""(t) => {
      document.querySelectorAll('.msg').forEach(e => e.remove());
      window.__last = renderMsg('gal', t, '11:40:36');
    }""", TEXT)
    page.evaluate("""() => {
      const m = document.getElementById('messages');
      m.style.scrollBehavior = 'auto';
      m.scrollTop = m.scrollHeight;
    }""")
    page.wait_for_timeout(300)
    return page.evaluate("""() => {
      const div = window.__last;
      const pills = div.querySelector('.pills');
      const r = e => e.getBoundingClientRect().toJSON();
      return {inside: !!pills, pills: pills && r(pills), bubble: r(div.querySelector('.bubble')),
              view: r(document.getElementById('messages'))};
    }""")


def test_pills_live_inside_their_message(page):
    g = _geom(page)
    assert g["inside"], "pills must be appended inside the message element"


def test_pills_sit_under_the_bubble_left_aligned(page):
    g = _geom(page)
    assert g["pills"]["top"] >= g["bubble"]["bottom"] - 1
    assert abs(g["pills"]["left"] - g["bubble"]["left"]) <= 2


def test_pills_visible_after_scroll_to_bottom(page):
    g = _geom(page)
    assert g["view"]["top"] <= g["pills"]["top"] and g["pills"]["bottom"] <= g["view"]["bottom"] + 1
