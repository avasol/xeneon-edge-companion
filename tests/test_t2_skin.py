"""T2 presentation acceptance; retain the data-only skin security boundary."""
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('t2_builder', ROOT / 'build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_t2_skin_valid_and_packaged(tmp_path):
    skin = builder.load_skin(ROOT / 'skins' / 't2')
    assert skin['id'] == 't2'
    assert skin['images']['portrait']
    path = builder.build(ROOT / 'skins' / 't2', tmp_path)
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('manifest.json'))
        assert manifest['id'] == 'com.aedelgard.edge.t2'
        assert 'resources/icon.png' in z.namelist()
        assert b'"id": "t2"' in z.read('index.html')


def test_skin_stays_data_only():
    folder = ROOT / 'skins' / 't2'
    assert folder.is_dir()
    assert not any(p.suffix.lower() in {'.js', '.css', '.html', '.svg'} for p in folder.rglob('*'))


def test_t2_presentation_contract():
    text = (ROOT / 'index.html').read_text(encoding='utf-8')
    for marker in ['t2-mode', 't2-backplate', 't2-flip', 'prefers-reduced-motion', 't2-scan', 't2-chrome']:
        assert marker in text
    assert 'aria-expanded' in text
    assert 'visibilitychange' in text


def test_existing_skins_still_build(tmp_path):
    for name in ['aedelgard', 'galadriel']:
        assert builder.build(ROOT / 'skins' / name, tmp_path).exists()
