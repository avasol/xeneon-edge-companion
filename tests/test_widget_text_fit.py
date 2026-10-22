"""Guard the complete shrink chain: grid -> panel -> message -> body."""
import re
from pathlib import Path
HTML = (Path(__file__).resolve().parents[1] / 'index.html').read_text()
def rule(selector):
    matches = re.findall(re.escape(selector) + r'\s*\{([^}]+)\}', HTML)
    assert matches, selector
    return ' '.join(matches)
def test_center_grid_track_can_shrink():
    assert re.search(r'grid-template-columns:\s*var\(--w-left\)\s+minmax\(0,\s*1fr\)\s+var\(--w-right\)', rule('#main'))
def test_chat_panel_can_shrink():
    assert re.search(r'min-width:\s*0', rule('#chat-panel'))
def test_message_body_can_shrink_without_shrinking_avatar():
    # Applies equally to normal, streamed, error and approval wrappers.
    assert re.search(r'min-width:\s*0', rule('.msg > div:last-child'))
    assert re.search(r'flex-shrink:\s*0', rule('.msg-avatar'))
def test_message_itself_can_shrink():
    assert re.search(r'min-width:\s*0', rule('.msg'))
def test_wide_tables_keep_local_scrolling():
    assert re.search(r'overflow-x:\s*auto', rule('.bubble .table-wrap'))
    assert re.search(r'overflow-x:\s*auto', rule('.bubble pre'))
