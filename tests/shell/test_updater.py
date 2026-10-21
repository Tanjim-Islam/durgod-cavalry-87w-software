import hashlib

from engine.shell.updater import Updater, parse_version

DATA = b"new setup"
RELEASE = {"tag_name": "v1.2.0", "html_url": "https://github.com/x/releases/tag/v1.2.0", "assets": [
    {"name": "Cavalry87-v1.2.0-portable.exe", "browser_download_url": "https://d/portable"},
    {"name": "Cavalry87-Setup-v1.2.0.exe", "browser_download_url": "https://d/setup",
     "digest": "sha256:" + hashlib.sha256(DATA).hexdigest()}]}


def make(installed=True, release=RELEASE, data=DATA, fail=None):
    pushed, launched, opened = [], [], []

    def fetch(url):
        if fail:
            raise OSError(fail)
        return release

    def download(url, dest, on_progress):
        on_progress(0.5)
        on_progress(1.0)
        dest.write_bytes(data)
        return hashlib.sha256(data).hexdigest()
    u = Updater("1.0.2", push=lambda n, p: pushed.append(p["status"]), installed=installed, fetch=fetch,
                download=download, launch=launched.append, open_url=opened.append, spawn=lambda fn: fn())
    return u, pushed, launched, opened


def test_versions_compare_as_numbers():
    assert parse_version("v1.10.0") > parse_version("1.9.9") and parse_version("1.0.2") == (1, 0, 2)


def test_check_finds_a_newer_release():
    u, pushed, _, _ = make()
    u.check()
    s = u.snapshot()
    assert s["status"] == "available" and s["latest"] == "1.2.0" and pushed == ["checking", "available"]


def test_check_says_up_to_date_and_handles_being_offline():
    u, _, _, _ = make(release={**RELEASE, "tag_name": "v1.0.2"})
    assert u.check() and u.snapshot()["status"] == "current"
    u, _, _, _ = make(fail="no internet")
    u.check()
    assert u.snapshot()["status"] == "error" and "internet" in u.snapshot()["error"]


def test_install_downloads_verifies_and_runs_setup():
    u, pushed, launched, _ = make()
    u.check()
    u.install()
    assert u.snapshot()["status"] == "installing" and launched and launched[0].name == "Cavalry87-Setup-v1.2.0.exe"
    assert "downloading" in pushed


def test_a_tampered_download_is_never_run():
    u, _, launched, _ = make(data=b"something else")
    u._download = lambda url, dest, p: (dest.write_bytes(b"x"), hashlib.sha256(b"x").hexdigest())[1]
    u.check()
    u.install()
    s = u.snapshot()
    assert not launched and s["status"] == "available" and "checksum" in s["error"]


def test_portable_copy_opens_the_release_page_instead():
    u, _, launched, opened = make(installed=False)
    u.check()
    u.install()
    assert not launched and opened == [RELEASE["html_url"]]


def test_no_second_check_while_one_runs():
    u, pushed, _, _ = make()
    u.state["status"] = "downloading"
    u.check()
    assert pushed == [] and u.snapshot()["status"] == "downloading"
