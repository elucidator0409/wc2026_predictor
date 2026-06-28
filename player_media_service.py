"""Fetch player photos / shirt numbers from external APIs with caching."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests
import streamlit as st

from players_service import player_initials

THESPORTSDB_KEY = "3"
REQUEST_TIMEOUT = 8


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text if text.lower() not in ("none", "null") else ""


def _fetch_thesportsdb(search_name: str, fifa_code: str, team_name: str) -> dict[str, Any]:
    url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}/searchplayers.php?p={quote(search_name)}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    players = (resp.json() or {}).get("player") or []
    if isinstance(players, dict):
        players = [players]

    code = fifa_code.upper()
    team_lower = team_name.lower()
    best = None
    best_score = -1
    for p in players:
        if not isinstance(p, dict):
            continue
        score = 0
        nat = _clean(p.get("strNationality")).lower()
        team = _clean(p.get("strTeam")).lower()
        if code and code in (_clean(p.get("strTeamShort")).upper(), _clean(p.get("strTeamBadge"))):
            score += 2
        if team_lower and team_lower in team:
            score += 3
        if team_lower and team_lower in nat:
            score += 4
        if search_name.lower() in _clean(p.get("strPlayer")).lower():
            score += 2
        if score > best_score:
            best_score = score
            best = p

    if not best and players:
        best = players[0]
    if not best:
        return {}

    photo = _clean(best.get("strCutout")) or _clean(best.get("strThumb"))
    return {
        "photo_url": photo,
        "shirt_number": _clean(best.get("strNumber")),
        "club_badge_url": _clean(best.get("strTeamBadge")),
        "source": "thesportsdb" if photo else "",
    }


def _fetch_wikipedia_thumb(search_name: str) -> str:
    search_url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={quote(search_name + ' footballer')}"
        "&format=json&srlimit=1"
    )
    resp = requests.get(search_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    hits = (resp.json() or {}).get("query", {}).get("search") or []
    if not hits:
        return ""

    title = hits[0].get("title", "")
    if not title:
        return ""

    img_url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&titles={quote(title)}&prop=pageimages&format=json&pithumbsize=120"
    )
    resp = requests.get(img_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    pages = (resp.json() or {}).get("query", {}).get("pages") or {}
    for page in pages.values():
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            return str(thumb)
    return ""


def fetch_player_media_impl(
    search_name: str,
    fifa_code: str = "",
    team_name: str = "",
) -> dict[str, Any]:
    """
    Pure fetch (no Streamlit cache). Returns photo_url, shirt_number, club_badge_url, initials, source.
    """
    search_name = _clean(search_name)
    if not search_name:
        return {
            "photo_url": "",
            "shirt_number": "",
            "club_badge_url": "",
            "initials": "?",
            "source": "initials",
        }

    initials = player_initials(search_name)
    result: dict[str, Any] = {
        "photo_url": "",
        "shirt_number": "",
        "club_badge_url": "",
        "initials": initials,
        "source": "initials",
    }

    try:
        tsdb = _fetch_thesportsdb(search_name, fifa_code, team_name)
        if tsdb.get("photo_url"):
            result.update(tsdb)
            result["initials"] = initials
            result["source"] = "thesportsdb"
            return result
    except Exception:
        pass

    try:
        wiki_photo = _fetch_wikipedia_thumb(search_name)
        if wiki_photo:
            result["photo_url"] = wiki_photo
            result["source"] = "wikipedia"
    except Exception:
        pass

    return result


@st.cache_data(ttl=604800, show_spinner=False)
def fetch_player_media(search_name: str, fifa_code: str = "", team_name: str = "") -> dict[str, Any]:
    """Cached wrapper for UI — 7 day TTL per (search_name, fifa_code)."""
    return fetch_player_media_impl(search_name, fifa_code, team_name)


def enrich_xi_with_media(xi: list[dict], fifa_code: str, team_name: str) -> list[dict]:
    """Attach media dict to each XI entry (uses cached fetch). Names from lineup Sheet."""
    enriched: list[dict] = []
    for entry in xi:
        player = entry.get("player") or {}
        search_name = (entry.get("search_name") or str(player.get("player_name", ""))).strip()
        media = fetch_player_media(search_name, fifa_code, team_name)
        shirt = str(player.get("shirt_number") or media.get("shirt_number") or "").strip()
        if shirt:
            media = {**media, "shirt_number": shirt}
        enriched.append({**entry, "search_name": search_name, "media": media})
    return enriched
