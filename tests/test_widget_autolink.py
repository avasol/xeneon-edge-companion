"""Bare URLs open the link sheet too (aedelgard-body docs/SPEC_convoy3.md S4)."""
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
TEXT = ("See https://aedelgard.com/download. Also [docs](https://aedelgard.com/docs), "
        "`https://in.code/x` and (https://paren.example/a).\n\n```\nhttps://fenced.example/y\n```\n\n"
        "[IMG]:https://img.example/p.png")


@pytest.fixture(scope="module")
def links():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-sandbox"])
        except Exception as e:
            pytest.fail(f"chromium is required for these tests: {e}")
        pg = b.new_page(viewport={"width": 2560, "height": 720})
        pg.goto((ROOT / "index.html").as_uri())
        pg.wait_for_timeout(300)
        out = pg.evaluate("""(t)=>{const d=document.createElement('div');
            d.innerHTML=renderMarkdown(t,'');
            return {links:[...d.querySelectorAll('a')].map(a=>({href:a.dataset.href||null,
                raw:a.getAttribute('href'), onclick:a.getAttribute('onclick')||'',
                inCode:!!a.closest('code,pre')})),
                imgs:[...d.querySelectorAll('img')].map(i=>i.getAttribute('src'))}}""", TEXT)
        b.close()
        return out


def test_bare_url_opens_the_sheet(links):
    hrefs = [l["href"] for l in links["links"]]
    assert "https://aedelgard.com/download" in hrefs
    assert "https://paren.example/a" in hrefs
    for l in links["links"]:
        assert "openLinkSheet(" in l["onclick"]
        assert l["raw"] is None
        assert not l["inCode"]


def test_markdown_link_is_not_doubled(links):
    hrefs = [l["href"] for l in links["links"]]
    assert hrefs.count("https://aedelgard.com/docs") == 1


def test_code_and_media_stay_untouched(links):
    hrefs = [l["href"] for l in links["links"]]
    assert not any("in.code" in h or "fenced.example" in h or "img.example" in h for h in hrefs)
    assert links["imgs"] == ["https://img.example/p.png"]
