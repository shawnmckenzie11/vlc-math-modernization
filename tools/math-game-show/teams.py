#!/usr/bin/env python3
"""Random and balanced (snake-draft) team assignment for Math Game Show."""

from __future__ import annotations

import random
from typing import Any, Sequence, TypeVar

T = TypeVar("T")


def assign_random(items: Sequence[T], n_teams: int, rng: random.Random | None = None) -> list[list[T]]:
    """Deal shuffled present students round-robin into ``n_teams`` teams.

    Args:
        items: Present students (or any hashable/objects).
        n_teams: Number of teams (>= 1).
        rng: Optional random source (tests inject a seeded Random).

    Returns:
        List of team member lists (may include empty teams if n > len(items)).

    Raises:
        ValueError: If ``n_teams`` is less than 1.
    """
    if n_teams < 1:
        raise ValueError("Need at least 1 team")
    pool = list(items)
    (rng or random).shuffle(pool)
    teams: list[list[T]] = [[] for _ in range(n_teams)]
    for index, item in enumerate(pool):
        teams[index % n_teams].append(item)
    return teams


def assign_balanced(
    items: Sequence[T],
    n_teams: int,
    totals: Sequence[int],
) -> list[list[T]]:
    """Snake-draft present students sorted by career TOTAL (high first).

    Order is 0, 1, …, n-1, n-1, …, 0, 0, … so similar scores land on
    different teams. Ties keep the incoming relative order (stable sort).

    Args:
        items: Present students.
        n_teams: Number of teams (>= 1).
        totals: Career individual TOTAL aligned with ``items``.

    Returns:
        List of team member lists.

    Raises:
        ValueError: If lengths disagree or ``n_teams`` is less than 1.
    """
    if n_teams < 1:
        raise ValueError("Need at least 1 team")
    if len(items) != len(totals):
        raise ValueError("items and totals must be the same length")
    ranked = sorted(range(len(items)), key=lambda i: (-int(totals[i]), i))
    teams: list[list[T]] = [[] for _ in range(n_teams)]
    direction = 1
    slot = 0
    for index in ranked:
        teams[slot].append(items[index])
        slot += direction
        if slot == n_teams:
            slot = n_teams - 1
            direction = -1
        elif slot < 0:
            slot = 0
            direction = 1
    return teams


def validate_team_count(n_teams: int, present_count: int) -> None:
    """Reject team counts that cannot run a game.

    Args:
        n_teams: Requested team count.
        present_count: Number of present students.

    Raises:
        ValueError: If the count is out of range.
    """
    if present_count < 1:
        raise ValueError("Mark at least one student present")
    if n_teams < 2:
        raise ValueError("Need at least 2 teams")
    if n_teams > present_count:
        raise ValueError("Cannot have more teams than present students")


TEAM_COLORS: tuple[str, ...] = (
    "#c8102e",
    "#0b3d91",
    "#ffb81c",
    "#00843d",
    "#7b2d8e",
    "#e87722",
    "#00a3e0",
    "#5c3317",
)


def color_for_team(sort_order: int) -> str:
    """Return an ESPN-bar color for a 0-based team index.

    Args:
        sort_order: Team slot (0 = Team 1).
    """
    return TEAM_COLORS[sort_order % len(TEAM_COLORS)]


def default_team_name(sort_order: int) -> str:
    """Default display name ``Team N`` (1-based).

    Args:
        sort_order: Team slot (0 = Team 1).
    """
    return f"Team {sort_order + 1}"


def membership_payload(teams: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    """Describe an assignment as JSON-friendly team buckets.

    Args:
        teams: Output of :func:`assign_random` or :func:`assign_balanced`
            where members are student id ints (or objects with ``id``).

    Returns:
        List of ``{sort_order, name, color, student_ids}``.
    """
    payload: list[dict[str, Any]] = []
    for order, members in enumerate(teams):
        student_ids: list[int] = []
        for member in members:
            if isinstance(member, int):
                student_ids.append(member)
            else:
                student_ids.append(int(member["id"] if isinstance(member, dict) else member.id))
        payload.append(
            {
                "sort_order": order,
                "name": default_team_name(order),
                "color": color_for_team(order),
                "student_ids": student_ids,
            }
        )
    return payload
