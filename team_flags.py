"""Team flag helpers — maps FIFA codes from teams.csv to flagcdn images & emoji."""

from __future__ import annotations

import html

import pandas as pd

# FIFA 3-letter code → flagcdn.com slug (ISO 3166-1 alpha-2 or special subregions)
FIFA_TO_FLAGCDN: dict[str, str] = {
    "MEX": "mx",
    "RSA": "za",
    "KOR": "kr",
    "CZE": "cz",
    "CAN": "ca",
    "BIH": "ba",
    "QAT": "qa",
    "SUI": "ch",
    "BRA": "br",
    "MAR": "ma",
    "HAI": "ht",
    "SCO": "gb-sct",
    "USA": "us",
    "PAR": "py",
    "AUS": "au",
    "TUR": "tr",
    "GER": "de",
    "CUR": "cw",
    "CIV": "ci",
    "ECU": "ec",
    "NED": "nl",
    "JPN": "jp",
    "SWE": "se",
    "TUN": "tn",
    "BEL": "be",
    "EGY": "eg",
    "IRN": "ir",
    "NZL": "nz",
    "ESP": "es",
    "CPV": "cv",
    "KSA": "sa",
    "URU": "uy",
    "FRA": "fr",
    "SEN": "sn",
    "IRQ": "iq",
    "NOR": "no",
    "ARG": "ar",
    "ALG": "dz",
    "AUT": "at",
    "JOR": "jo",
    "POR": "pt",
    "COD": "cd",
    "UZB": "uz",
    "COL": "co",
    "ENG": "gb-eng",
    "CRO": "hr",
    "GHA": "gh",
    "PAN": "pa",
}

TBD_FLAG = "⚽"


def build_name_to_fifa(teams_df: pd.DataFrame) -> dict[str, str]:
    if teams_df is None or teams_df.empty:
        return {}
    lookup: dict[str, str] = {}
    for _, row in teams_df.iterrows():
        name = str(row.get("team_name", "")).strip()
        code = str(row.get("fifa_code", "")).strip().upper()
        if name and code:
            lookup[name] = code
    lookup["TBD"] = ""
    return lookup


def resolve_fifa_code(
    fifa_code: str | None = None,
    team_name: str | None = None,
    name_to_fifa: dict[str, str] | None = None,
) -> str | None:
    if fifa_code and str(fifa_code).strip():
        return str(fifa_code).strip().upper()
    if team_name and name_to_fifa:
        code = name_to_fifa.get(str(team_name).strip(), "")
        return code.upper() if code else None
    return None


def flagcdn_slug(fifa_code: str | None) -> str | None:
    if not fifa_code:
        return None
    code = str(fifa_code).strip().upper()
    return FIFA_TO_FLAGCDN.get(code)


def flag_emoji(
    fifa_code: str | None = None,
    team_name: str | None = None,
    name_to_fifa: dict[str, str] | None = None,
) -> str:
    code = resolve_fifa_code(fifa_code, team_name, name_to_fifa)
    slug = flagcdn_slug(code)
    if not slug:
        return TBD_FLAG
    if len(slug) == 2 and slug.isalpha():
        return _iso2_to_emoji(slug)
    if slug == "gb-eng":
        return "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
    if slug == "gb-sct":
        return "🏴󠁧󠁢󠁳󠁣󠁴󠁿"
    return TBD_FLAG


def _iso2_to_emoji(iso2: str) -> str:
    iso2 = iso2.upper()
    if len(iso2) != 2 or not iso2.isalpha():
        return TBD_FLAG
    return "".join(chr(127397 + ord(c)) for c in iso2)


def flag_img_html(
    fifa_code: str | None = None,
    team_name: str | None = None,
    name_to_fifa: dict[str, str] | None = None,
    size: str = "md",
) -> str:
    code = resolve_fifa_code(fifa_code, team_name, name_to_fifa)
    slug = flagcdn_slug(code)
    if not slug:
        return f'<span class="team-flag team-flag--{size} team-flag--tbd" aria-hidden="true">{TBD_FLAG}</span>'
    src = f"https://flagcdn.com/24x18/{slug}.png"
    src2x = f"https://flagcdn.com/48x36/{slug}.png"
    return (
        f'<img class="team-flag team-flag--{size}" '
        f'src="{html.escape(src)}" srcset="{html.escape(src2x)} 2x" '
        f'alt="" loading="lazy" decoding="async" />'
    )


def team_line_html(
    team_name: str,
    side: str,
    fifa_code: str | None = None,
    name_to_fifa: dict[str, str] | None = None,
) -> str:
    """side: 'a' = flag left of name, 'b' = flag right of name."""
    safe_name = html.escape(str(team_name))
    title_attr = f' title="{safe_name}"' if safe_name else ""
    flag = flag_img_html(fifa_code=fifa_code, team_name=team_name, name_to_fifa=name_to_fifa)
    if side == "b":
        inner = f'<span class="team-line-name"{title_attr}>{safe_name}</span>{flag}'
    else:
        inner = f'{flag}<span class="team-line-name"{title_attr}>{safe_name}</span>'
    return f'<span class="team-line team-line--{html.escape(side)}">{inner}</span>'
