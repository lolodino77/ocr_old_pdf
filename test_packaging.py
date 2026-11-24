"""Tests de la version portable (packaging/), sans Internet : contenu des trois paquets, cloisonnement des systèmes,
vérification rapide, données de l'utilisateur.

    python -m unittest test_packaging
"""
import ast
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "packaging"))
sys.path.insert(0, str(ROOT / "packaging" / "common"))
import build_package  # noqa: E402
import manifest as M  # noqa: E402
from system_base import available, load  # noqa: E402

SYSTEMS = ["linux", "macos", "windows"]


def code_without_docs(path: Path) -> str:
    """Code d'un fichier Python sans ses docstrings ni ses commentaires (ast.unparse les retire)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            body.pop(0)
    return ast.unparse(tree)


class Systems(unittest.TestCase):
    """Cloisonnement : le tronc commun ne connaît aucun système ; chaque système est complet dans son dossier."""

    def test_three_systems_available(self):
        self.assertEqual(available(), SYSTEMS)

    def test_each_system_is_complete(self):
        for name in SYSTEMS:
            system = load(name)
            self.assertEqual(system.NAME, name)
            self.assertTrue((system.folder / system.LAUNCHER).is_file(), name)
            self.assertTrue((system.folder / system.NOTICE).is_file(), name)
            self.assertTrue(system.LABEL and system.TEXT_SUFFIXES, name)

    def test_common_code_knows_no_system(self):
        forbidden = [".bat", ".sh", ".command", "powershell", "osascript", ".desktop", "onedrive", "icloud",
                     "sys.platform", "os.name", "win-64", "linux-64", "osx-"]
        files = list((ROOT / "packaging" / "common").glob("*.py")) + [ROOT / "packaging" / "build_package.py"]
        import re
        for path in files:
            code = code_without_docs(path).lower()
            found = [token for token in forbidden if re.search(re.escape(token) + (r"\b" if token[-1].isalnum() else ""), code)]
            if path.name == "system_base.py":  # seul endroit qui traduit sys.platform en nom de dossier
                found = [t for t in found if t != "sys.platform"]
            self.assertEqual(found, [], f"{path.name} contient du code propre à un système : {found}")

    def test_launchers_have_the_right_line_endings_in_the_repository(self):
        self.assertIn(b"\r\n", (load("windows").folder / load("windows").LAUNCHER).read_bytes())
        for name in ("linux", "macos"):
            self.assertNotIn(b"\r\n", (load(name).folder / load(name).LAUNCHER).read_bytes(), name)

    def test_tesseract_location_per_system(self):
        tools = Path("outils")
        self.assertEqual(load("windows").tesseract(tools), tools / "Library" / "bin" / "tesseract.exe")
        self.assertEqual(load("linux").tesseract(tools), tools / "bin" / "tesseract")
        self.assertEqual(load("macos").tesseract(tools), tools / "bin" / "tesseract")
        self.assertFalse(load("windows").NEEDS_BROWSER_DOWNLOAD)  # Edge est toujours là
        self.assertTrue(load("linux").NEEDS_BROWSER_DOWNLOAD and load("macos").NEEDS_BROWSER_DOWNLOAD)

    def test_old_mac_skips_the_browser(self):
        """macOS 10.14 (Mojave) : le navigateur de Playwright ne démarre pas, son téléchargement est sauté avec un
        avertissement qui mène au mode API ; macOS 11 et plus : téléchargé normalement."""
        from unittest import mock

        mac = load("macos")
        module = sys.modules[type(mac).__module__]
        for version, skipped in (("10.14.6", True), ("10.15.7", True), ("11.7.10", False), ("14.5", False), ("", False)):
            with mock.patch.object(module.platform, "mac_ver", return_value=(version, ("", "", ""), "")):
                reason = mac.browser_unavailable()
            self.assertEqual(bool(reason), skipped, version)
            if skipped:
                self.assertIn("API Gemini", reason)
        self.assertIsNone(load("linux").browser_unavailable())

    def test_old_mac_requirements(self):
        """requirements.txt : sur macOS < 13 (Darwin < 22), versions qui existent toutes faites pour macOS 10.14."""
        from packaging.requirements import Requirement

        def chosen(release, machine="x86_64", platform="darwin"):
            env = {"sys_platform": platform, "platform_release": release, "platform_machine": machine}
            pins = {}
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#"):
                    r = Requirement(line)
                    if r.marker is None or r.marker.evaluate(env):
                        self.assertNotIn(r.name, pins, f"{r.name} en double pour {platform} {release}")
                        pins[r.name] = str(r.specifier)
            return pins

        mojave, ventura, windows = chosen("18.7.0"), chosen("22.6.0", "arm64"), chosen("10", "AMD64", "win32")
        self.assertEqual([mojave[n] for n in ("pypdfium2", "pyarrow", "numpy", "playwright")],
                         ["==4.30.1", "==14.0.2", "==1.26.4", "==1.40.0"])
        self.assertEqual(chosen("20.6.0")["playwright"], "==1.64.1")
        for pins in (ventura, windows):
            self.assertEqual([pins[n] for n in ("pypdfium2", "pyarrow", "numpy", "playwright")],
                             ["==5.15.2", "==21.0.0", "==2.3.4", "==1.64.1"])


class Packages(unittest.TestCase):
    """Contenu des paquets, fabriqués à partir de tous les fichiers du programme présents sur le disque."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        everything = {f.relative_to(ROOT).as_posix() for f, _ in M.program_files(ROOT)}
        cls.zips = {name: build_package.build(name, Path(cls.tmp.name), tracked=everything) for name in SYSTEMS}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def names(self, name):
        with zipfile.ZipFile(self.zips[name]) as z:
            return z.namelist()

    def test_package_layout(self):
        for name in SYSTEMS:
            system = load(name)
            folder = f"{M.PACKAGE_NAME}-{system.LABEL}"
            names = self.names(name)
            self.assertIn(f"{folder}/{system.LAUNCHER}", names)
            self.assertIn(f"{folder}/{system.NOTICE}", names)
            self.assertIn(f"{folder}/programme/{M.VERSION_FILE}", names)
            for item in M.APP_ITEMS:
                self.assertTrue(any(n == f"{folder}/programme/{item}" or n.startswith(f"{folder}/programme/{item}/")
                                    for n in names), f"{name} : {item} absent")

    def test_nothing_from_other_systems_nor_developer_tools(self):
        for name in SYSTEMS:
            for n in self.names(name):
                parts = n.split("/")
                if len(parts) > 3 and parts[2] == "packaging":
                    self.assertIn(parts[3], {"common", "assets", name, "build_package.py", "README.md"}, f"{name} : {n}")

    def test_no_user_data(self):
        for name in SYSTEMS:
            for n in self.names(name):
                rel = n.split("/", 2)[2] if n.count("/") >= 2 and "/programme/" in n else ""
                if rel:
                    self.assertFalse(M.is_user_data(rel) and rel != M.VERSION_FILE, f"{name} : {n}")
                self.assertFalse(n.endswith("/.env"), n)

    def test_launcher_line_endings_and_permissions(self):
        for name in SYSTEMS:
            system = load(name)
            with zipfile.ZipFile(self.zips[name]) as z:
                info = z.getinfo(f"{M.PACKAGE_NAME}-{system.LABEL}/{system.LAUNCHER}")
                data = z.read(info)
                notice = z.read(f"{M.PACKAGE_NAME}-{system.LABEL}/{system.NOTICE}")
            executable = bool((info.external_attr >> 16) & 0o111)
            self.assertEqual(executable, system.EXECUTABLE, name)
            if system.EOL == b"\r\n":
                self.assertNotIn(b"\n", data.replace(b"\r\n", b""), name)
                self.assertTrue(notice.startswith(b"\xef\xbb\xbf"), "notice Windows sans BOM")
            else:
                self.assertNotIn(b"\r\n", data, name)

    def test_check_says_preparation_needed_on_a_fresh_folder(self):
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(self.zips["windows"]) as z:
            z.extractall(tmp)
            programme = Path(tmp) / f"{M.PACKAGE_NAME}-Windows" / "programme"
            r = subprocess.run([sys.executable, str(programme / "packaging" / "common" / "prepare.py"),
                                "--root", str(programme), "--check"], capture_output=True)
            if sys.platform.startswith("win"):
                self.assertEqual(r.returncode, 10)  # NOT_READY


class UserData(unittest.TestCase):
    def test_outputs_and_runtime_are_user_data(self):
        for rel in [".venv/x", "runtime/outils/x", ".env", "logs/run.log", "Doc_modernized_cleaned_text.docx",
                    "Doc_ocr_text.txt", "Doc.pdf", "pdf_uploads/a.pdf", "installation.json", "instance.json",
                    "modernisateur.log", "browser_profile/x"]:
            self.assertTrue(M.is_user_data(rel), rel)
        for rel in ["app.py", "packaging/common/prepare.py", ".env.example", "requirements.txt"]:
            self.assertFalse(M.is_user_data(rel), rel)


if __name__ == "__main__":
    unittest.main()
