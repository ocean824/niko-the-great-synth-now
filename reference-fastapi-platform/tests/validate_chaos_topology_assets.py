from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def require(content: str, values: list[str], artifact: str) -> None:
    missing = [value for value in values if value not in content]
    assert not missing, f"{artifact} missing: {', '.join(missing)}"


def main() -> None:
    game_day = read("docs/chaos_engineering_game_day.md")
    require(
        game_day,
        [
            "staging-only",
            "No experiment may target production",
            "Gremlin-managed game day",
            "LitmusChaos",
            "Immediate stop procedure",
            "GD-1: Primary-region application isolation simulation",
            "GD-2: Database-path latency injection",
            "GD-3: Secondary-region readiness and recovery validation",
            "traffic-steering",
            "synthetic=true",
        ],
        "Chaos Engineering game-day plan",
    )

    mermaid = read("docs/multi_region_topology.mmd")
    require(
        mermaid,
        [
            "Primary AWS Region",
            "Secondary AWS Region",
            "Aurora PostgreSQL + pgvector",
            "ElastiCache Redis",
            "Encrypted S3",
            "ECR",
            "EKS OIDC / IRSA",
            "Global traffic steering",
            "global replication",
        ],
        "Mermaid topology source",
    )

    html = read("docs/interactive_multi_region_topology.html")
    require(
        html,
        [
            "Multi-Region AWS Topology",
            "data-filter=\"primary\"",
            "data-filter=\"secondary\"",
            "data-filter=\"replication\"",
            "selectNode",
            "Aurora PostgreSQL + pgvector writer",
            "Global traffic steering",
            "not Terraform-provisioned",
            "GD-2 injects limited database-path latency",
        ],
        "Interactive topology map",
    )

    png = ROOT / "docs/multi_region_topology.png"
    assert png.exists() and png.stat().st_size > 100_000, "Rendered topology PNG is absent or implausibly small"
    print("Chaos game-day and topology asset validation passed")


if __name__ == "__main__":
    main()
