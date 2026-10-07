"""Ten ready-made cases for the dashboard: `uv run python -m backend.demo_cases [--owner EMAIL]`.

Each case is a workspace holding a baseline plus the options a pricing team would actually weigh,
including a few that lose and a few the engine must refuse. Every figure still comes from the engine;
this file only chooses lever settings. Seeding skips a case whose name already exists.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from backend import activity, db
from backend.engine.scenario import CostShock, Lever, Scenario

CAN, PET, BOTTLE, PACK6 = (
    f"Aurora-{f}" for f in ("can_330ml", "pet_500ml", "bottle_1500ml", "multipack_6x330ml")
)
ALL = (CAN, PET, BOTTLE, PACK6)


def price(*skus: str, to: float) -> dict[str, Lever]:
    return {s: Lever(price_index=to) for s in skus}


def promo(
    *skus: str, depth: float, mechanic: str = "TPR", weeks: float = 2, at: float = 1.0
) -> dict[str, Lever]:
    return {
        s: Lever(
            price_index=at, promo_depth_pct=depth, mechanic=mechanic, promo_weeks_per_month=weeks
        )
        for s in skus
    }


def sc(name: str, levers: dict[str, Lever] | None = None, **cost: float) -> Scenario:
    return Scenario(name=name, levers=levers or {}, cost_shock=CostShock(**cost))


BASE = sc("Baseline")

# (name, question, scenarios, names the engine is expected to refuse)
CASES: list[tuple[str, str, list[Scenario], set[str]]] = [
    (
        "Protect margin against an 8% input-cost rise",
        "Aluminium, PET resin and sugar all rise 8%. Which price moves recover the most gross profit without losing too much volume?",
        [
            BASE,
            sc("Cost rise, no response", aluminium_pct=8, pet_resin_pct=8, sugar_pct=8),
            sc(
                "Cost rise, +3% on every pack",
                price(*ALL, to=1.03),
                aluminium_pct=8,
                pet_resin_pct=8,
                sugar_pct=8,
            ),
            sc(
                "Cost rise, +4% on cans and multipacks",
                price(CAN, PACK6, to=1.04),
                aluminium_pct=8,
                pet_resin_pct=8,
                sugar_pct=8,
            ),
            sc(
                "Cost rise, +6% on every pack",
                price(*ALL, to=1.06),
                aluminium_pct=8,
                pet_resin_pct=8,
                sugar_pct=8,
            ),
        ],
        set(),
    ),
    (
        "500ml PET price ladder",
        "How far can the 500ml PET price move up or down before profit stops improving? Includes an out-of-range request the engine should refuse.",
        [
            BASE,
            sc("PET -4%", price(PET, to=0.96)),
            sc("PET +2%", price(PET, to=1.02)),
            sc("PET +4%", price(PET, to=1.04)),
            sc("PET +6%", price(PET, to=1.06)),
            sc("PET +50% (out of range)", price(PET, to=1.5)),
        ],
        {"PET +50% (out of range)"},
    ),
    (
        "Weekend promotion on the 1.5L bottle",
        "Which promotion mechanic and depth gives the 1.5L bottle the best profit after pull-forward?",
        [
            BASE,
            sc("Bottle TPR 10%", promo(BOTTLE, depth=10)),
            sc("Bottle TPR 20%", promo(BOTTLE, depth=20)),
            sc(
                "Bottle feature and display 15%",
                promo(BOTTLE, depth=15, mechanic="feature_display"),
            ),
            sc("Bottle BOGO 20%", promo(BOTTLE, depth=20, mechanic="BOGO")),
        ],
        set(),
    ),
    (
        "Premium multipack push",
        "Is the 6x330ml multipack better served by a higher price or a promotion? Multipacks have no BOGO history, so that option should be refused.",
        [
            BASE,
            sc("Multipack +4%", price(PACK6, to=1.04)),
            sc("Multipack -4%", price(PACK6, to=0.96)),
            sc(
                "Multipack feature and display 10%",
                promo(PACK6, depth=10, mechanic="feature_display", weeks=1),
            ),
            sc("Multipack BOGO 15% (no history)", promo(PACK6, depth=15, mechanic="BOGO", weeks=1)),
        ],
        {"Multipack BOGO 15% (no history)"},
    ),
    (
        "Where to take price: can or PET",
        "A 4% price rise on one pack or both: which choice protects profit and loses the least volume?",
        [
            BASE,
            sc("Cans +4%", price(CAN, to=1.04)),
            sc("PET +4%", price(PET, to=1.04)),
            sc("Cans and PET +4%", price(CAN, PET, to=1.04)),
            sc("Cans and PET +2%", price(CAN, PET, to=1.02)),
        ],
        set(),
    ),
    (
        "Respond to a competitor price war",
        "Rivals cut prices. Compare holding price, a small cut, a cut with a promotion, and a deep cut the data cannot support.",
        [
            BASE,
            sc("Cut PET 3%", price(PET, to=0.97)),
            sc("Cut every pack 3%", price(*ALL, to=0.97)),
            sc(
                "Cut cans 5% and promote 10%",
                {
                    CAN: Lever(
                        price_index=0.95,
                        promo_depth_pct=10,
                        mechanic="TPR",
                        promo_weeks_per_month=2,
                    )
                },
            ),
            sc("Cut every pack 20% (out of range)", price(*ALL, to=0.8)),
        ],
        {"Cut every pack 20% (out of range)"},
    ),
    (
        "Summer volume push",
        "Which promotion lifts volume most without giving away profit? Includes a deep promotion at a raised price, which the data does not cover.",
        [
            BASE,
            sc("Cans and PET TPR 15%", promo(CAN, PET, depth=15)),
            sc("Cans only TPR 20%", promo(CAN, depth=20)),
            sc(
                "Cans and PET feature and display 15%",
                promo(CAN, PET, depth=15, mechanic="feature_display"),
            ),
            sc("Deep promo with price rise (unsupported)", promo(CAN, depth=25, at=1.08)),
        ],
        {"Deep promo with price rise (unsupported)"},
    ),
    (
        "Aluminium price shock on cans and multipacks",
        "Aluminium rises 10%. Does a partial price pass-through beat absorbing it, or cutting promotions?",
        [
            BASE,
            sc("Aluminium +10%, absorb", aluminium_pct=10),
            sc(
                "Aluminium +10%, +3% on cans and multipacks",
                price(CAN, PACK6, to=1.03),
                aluminium_pct=10,
            ),
            sc(
                "Aluminium +10%, +5% on cans and multipacks",
                price(CAN, PACK6, to=1.05),
                aluminium_pct=10,
            ),
            sc("Aluminium +10%, promote cans 10%", promo(CAN, depth=10), aluminium_pct=10),
        ],
        set(),
    ),
    (
        "Trade-spend efficiency on 500ml PET",
        "At the same 10% depth, which promotion mechanic earns the most profit per rupee given away?",
        [
            BASE,
            sc("PET TPR 10%", promo(PET, depth=10)),
            sc("PET feature and display 10%", promo(PET, depth=10, mechanic="feature_display")),
            sc("PET BOGO 10%", promo(PET, depth=10, mechanic="BOGO")),
            sc("PET TPR 20%", promo(PET, depth=20)),
        ],
        set(),
    ),
    (
        "Shift mix toward larger packs",
        "Can a small price rise on cans, paired with value on the 1.5L bottle, move shoppers to bigger and more profitable packs?",
        [
            BASE,
            sc("Cans +4%", price(CAN, to=1.04)),
            sc("Cans +4%, bottle -2%", {**price(CAN, to=1.04), **price(BOTTLE, to=0.98)}),
            sc("Cans +4%, bottle promo 10%", {**price(CAN, to=1.04), **promo(BOTTLE, depth=10)}),
            sc("Bottle -4%", price(BOTTLE, to=0.96)),
        ],
        set(),
    ),
]


def seed(owner: str | None = None) -> list[str]:
    """Create any missing case; return the names created. Needs DATABASE_URL."""
    factory = db.get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    created: list[str] = []
    with factory() as session:
        email = owner or session.scalar(
            select(db.User.email).where(db.User.is_active.is_(True)).order_by(db.User.email)
        )
        if email is None:
            raise RuntimeError("no active user exists; create one with backend.auth_users first")
        existing = set(session.scalars(select(db.Workspace.name)))
        now = datetime.now(UTC)
        for name, question, scenarios, _refused in CASES:
            if name in existing:
                continue
            workspace = db.Workspace(
                id=uuid4().hex,
                name=name,
                description=question,
                created_by=email,
                updated_by=email,
                created_at=now,
                updated_at=now,
                archived=False,
            )
            state = db.WorkspaceState(
                workspace_id=workspace.id,
                scenarios=[s.model_dump(mode="json") for s in scenarios],
                version=1,
                updated_at=now,
            )
            session.add_all([workspace, state])
            created.append(name)
        session.commit()
    for name in created:
        activity.record(email, "workspace.create", None, {"name": name, "seeded": True})
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owner", help="Email to record as the creator (default: first active user)"
    )
    made = seed(parser.parse_args().owner)
    print(
        f"created {len(made)} case(s)"
        + (": " + "; ".join(made) if made else " (all already exist)")
    )
