import base64
from pathlib import Path

from argus_core.types import Screenshot, Ticket

PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\x02\xfe"
    b"\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG = b"\xff\xd8\xff\xe0argus"


def _ticket(path: str, media_type: str = "image/png") -> Ticket:
    return Ticket(
        id="sign-in",
        text="The Sign in button does nothing.",
        screenshot=Screenshot(media_type=media_type, path=path),
    )


def test_image_is_attached_only_in_image_mode(tmp_path: Path):
    from repro_agent.prompt import assemble_prompt

    (tmp_path / "shot.png").write_bytes(PNG)
    ticket = _ticket("shot.png")
    text = assemble_prompt(ticket, "text", tmp_path)
    image = assemble_prompt(ticket, "image", tmp_path)
    assert text.model_dump() == {
        "mode": "text",
        "text": "The Sign in button does nothing.",
        "image": None,
    }
    assert image.image is not None
    assert image.image.media_type == "image/png"
    assert base64.b64decode(image.image.data_base64) == PNG


def test_bytes_that_do_not_match_the_media_type_are_a_tool_error(tmp_path: Path):
    from repro_agent.prompt import assemble_prompt
    from repro_agent.tools import ToolError

    (tmp_path / "shot.png").write_bytes(JPEG)
    result = assemble_prompt(_ticket("shot.png", "image/png"), "image", tmp_path)
    assert isinstance(result, ToolError)
    assert result.ok is False
    assert result.error == "failed"
    text = assemble_prompt(_ticket("shot.png", "image/png"), "text", tmp_path)
    assert text.image is None
