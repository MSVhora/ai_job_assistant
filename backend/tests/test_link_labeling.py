from app.schemas.profile import StructuredProfile
from app.services.profile_extraction import _enrich_link_labels, _label_from_url


def test_known_domains_get_labels() -> None:
    assert _label_from_url("https://www.linkedin.com/in/janedoe") == "LinkedIn"
    assert _label_from_url("https://github.com/janedoe") == "GitHub"
    assert _label_from_url("https://gitlab.com/janedoe") == "GitLab"
    assert _label_from_url("https://x.com/janedoe") == "X"
    assert _label_from_url("https://scholar.google.com/citations?user=x") == "Google Scholar"


def test_unknown_or_bare_urls_fall_back_to_website() -> None:
    assert _label_from_url("https://janedoe.dev") == "Website"
    assert _label_from_url("janedoe.dev") == "Website"
    assert _label_from_url("not a url") == "Website"


def test_existing_labels_are_preserved() -> None:
    profile = StructuredProfile.model_validate(
        {
            "contact": {
                "full_name": "Jane Doe",
                "links": [
                    {"label": "My Portfolio", "url": "https://janedoe.dev"},
                    {"label": None, "url": "https://github.com/janedoe"},
                ],
            },
            "skills": ["SQL"],
        }
    )

    enriched = _enrich_link_labels(profile)

    assert enriched.contact.links[0].label == "My Portfolio"
    assert enriched.contact.links[1].label == "GitHub"
