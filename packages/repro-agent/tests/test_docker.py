import subprocess
from pathlib import Path

import pytest

IMAGE = "argus-repro:p1"
NET = "argus-repro-p1"
APP = "argus-p1-app"
ROOT = Path(__file__).resolve().parents[1] / "docker"
FORBIDDEN = ("page.evaluate", "browser_run_code_unsafe", "browser_evaluate")


def _run(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def test_image_sources_keep_unsafe_tools_off():
    for path in ROOT.iterdir():
        if path.suffix not in {".mjs", ".sh", ".json"} and path.name != "Dockerfile":
            continue
        text = path.read_text(encoding="utf-8")
        for word in FORBIDDEN:
            assert word not in text


@pytest.fixture(scope="module")
def image():
    build = _run(["docker", "build", "-t", IMAGE, str(ROOT)], timeout=900)
    assert build.returncode == 0, build.stderr[-2000:]
    _run(["docker", "rm", "-f", APP])
    _run(["docker", "network", "rm", NET])
    created = _run(["docker", "network", "create", "--internal", NET])
    assert created.returncode == 0, created.stderr
    yield IMAGE
    _run(["docker", "rm", "-f", APP])
    _run(["docker", "network", "rm", NET])


def _user_data_dir(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("user-data-dir="):
            return line.split("=", 1)[1]
    raise AssertionError(stdout)


def test_sample_script_returns_its_exit_code(image: str):
    result = _run(["docker", "run", "--rm", "--network", NET, "--ipc=host", image])
    assert result.returncode == 0, result.stderr[-2000:]
    assert _user_data_dir(result.stdout).startswith("/tmp/argus-user-data.")


def test_each_run_gets_its_own_user_data_dir(image: str):
    first = _run(["docker", "run", "--rm", "--network", NET, "--ipc=host", image])
    second = _run(["docker", "run", "--rm", "--network", NET, "--ipc=host", image])
    assert first.returncode == 0, first.stderr[-2000:]
    assert second.returncode == 0, second.stderr[-2000:]
    assert _user_data_dir(first.stdout) != _user_data_dir(second.stdout)


def test_container_cannot_reach_the_internet(image: str):
    result = _run(["docker", "run", "--rm", "--network", NET, image, "probe-net.mjs"], timeout=30)
    assert result.returncode != 0


def test_container_can_reach_the_app(image: str):
    started = _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            APP,
            "--network",
            NET,
            "--entrypoint",
            "node",
            image,
            "-e",
            "require('http').createServer((q,s)=>{s.writeHead(200);s.end('ok')}).listen(8000,'0.0.0.0')",
        ]
    )
    assert started.returncode == 0, started.stderr
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            NET,
            "-e",
            f"ARGUS_APP_URL=http://{APP}:8000/",
            image,
            "probe-app.mjs",
        ],
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
