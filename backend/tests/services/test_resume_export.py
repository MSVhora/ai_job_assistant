import json
import uuid

from fakes import golden_profile

from app.schemas.resume_document import Bullet, ResumeContent
from app.services.resume_export import to_json_resume, to_markdown, to_plain_text
from app.services.resume_mapping import profile_to_content

PRIVATE_BULLET = Bullet(
    text="Built a private ingestion layer",
    achievement_id=uuid.uuid4(),
    evidence_ids=[uuid.uuid4()],
    metric_ids=["m1"],
    from_private=True,
    score=0.91,
    origin="generated",
    check="needs_review",
)
FORBIDDEN = ("private", "Private", "from_private", "provenance", "needs_review", "generated")


def content_with_private_bullet() -> ResumeContent:
    content = profile_to_content(golden_profile())
    content.work[0].highlights.append(PRIVATE_BULLET)
    return content


def exports(content: ResumeContent) -> dict[str, str]:
    return {
        "text": to_plain_text(content),
        "markdown": to_markdown(content),
        "json": json.dumps(to_json_resume(content)),
    }


def test_every_bullet_appears_exactly_once_in_text_and_markdown() -> None:
    content = content_with_private_bullet()
    bullets = [b.text for job in content.work for b in job.highlights]
    bullets += [b.text for project in content.projects for b in project.highlights]

    rendered = exports(content)

    for bullet in bullets:
        assert rendered["text"].count(bullet) == 1
        assert rendered["markdown"].count(bullet) == 1


def test_contact_comes_from_the_document_basics() -> None:
    text = to_plain_text(content_with_private_bullet())

    assert text.splitlines()[0] == "Ada Lovelace"
    assert "ada@example.com | +44 20 7946 0000 | London, UK" in text
    assert "https://github.com/ada" in text


def test_no_private_marker_or_provenance_text_in_any_format() -> None:
    for name, output in exports(content_with_private_bullet()).items():
        scrubbed = output.replace("Built a private ingestion layer", "")
        assert not [word for word in FORBIDDEN if word in scrubbed], name
        assert str(PRIVATE_BULLET.achievement_id) not in output, name
        assert str(PRIVATE_BULLET.evidence_ids[0]) not in output, name


def test_exports_are_stable_across_two_calls() -> None:
    content = content_with_private_bullet()

    assert exports(content) == exports(content)


def test_json_resume_output_is_valid_json_with_flat_string_highlights() -> None:
    document = json.loads(exports(content_with_private_bullet())["json"])

    assert all(
        isinstance(line, str) for job in document["work"] for line in job.get("highlights", [])
    )
    assert document["basics"]["name"] == "Ada Lovelace"


def test_sections_use_standard_headings_in_order() -> None:
    text = to_plain_text(content_with_private_bullet())

    headings = [
        "SUMMARY",
        "EXPERIENCE",
        "EDUCATION",
        "SKILLS",
        "PROJECTS",
        "CERTIFICATIONS",
        "AWARDS",
        "LANGUAGES",
    ]
    positions = [text.index(f"\n{heading}\n") for heading in headings]
    assert positions == sorted(positions)


def test_current_role_without_an_end_date_reads_present() -> None:
    assert "Jul 2023 - Present" in to_plain_text(profile_to_content(golden_profile()))
