"""Exercise the actual SSE completion path, not only the standalone parser."""
import json
from pathlib import Path

import pytest

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('token', [False, True], ids=['direct-done', 'streamed-done'])
def test_final_reply_renders_clickable_pills(token):
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 2560, 'height': 720})
        page.goto((ROOT / 'index.html').as_uri())
        result = page.evaluate('''async ({token}) => {
          CFG.token = 'test-token';
          CFG.url = 'http://localhost';
          const reply = 'Answer.\\n\\n[[options: Trace the miner | Verify the survey records | Investigate both]]';
          const events = [];
          if (token) events.push({t:'token', v:'Answer.'});
          events.push({t:'done', v:reply, display_v:reply});
          window.fetch = async () => new Response(
            events.map(e => 'data: ' + JSON.stringify(e) + '\\n').join(''),
            {status:200, headers:{'Content-Type':'text/event-stream'}});
          document.getElementById('msg-input').value = 'test';
          await sendMessage();
          const msg = [...document.querySelectorAll('.msg.gal')].pop();
          return {text:msg.querySelector('.bubble').textContent,
                  labels:[...msg.querySelectorAll('.pill')].map(x => x.textContent),
                  copy:!!msg.querySelector('.btn-copy')};
        }''', {'token': token})
        browser.close()
    assert '[[options:' not in result['text']
    assert result['labels'] == ['Trace the miner', 'Verify the survey records', 'Investigate both']
    assert result['copy']
