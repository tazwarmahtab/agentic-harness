"""Usage examples for enhanced TAZ OS memory system.

Demonstrates:
1. Procedural Memory (skills/SOPs)
2. Memory Consolidation (episodic → semantic)
3. Dual Retrieval Strategy (RAG + SQL)
4. Memory Health Metrics
"""

from pathlib import Path
from tazos.memory import MemoryStore, ProceduralMemory


# =============================================================================
# Example 1: Procedural Memory — Skills and SOPs
# =============================================================================

def example_procedural_memory():
    """Load and retrieve procedural memory (skills/SOPs)."""

    # Initialize procedural memory
    proc_mem = ProceduralMemory(sop_root=Path("./sops"))

    # Add a procedure manually
    proc_mem.add_procedure(
        name="code_review_checklist",
        description="Standard code review checklist for PRs",
        content="""
# Code Review Checklist

1. **Functionality**: Does the code do what it's supposed to?
2. **Tests**: Are there tests? Do they cover edge cases?
3. **Security**: Any security vulnerabilities?
4. **Performance**: Any obvious performance issues?
5. **Readability**: Is the code clear and well-documented?
        """,
        tags=["code_review", "quality", "sop"],
        classification="internal",
    )

    # Load SOPs from a directory
    count = proc_mem.load_from_directory(Path("./sops"))
    print(f"Loaded {count} procedures from ./sops directory")

    # Search by tags
    qa_procedures = proc_mem.search_by_tags(["quality", "testing"])
    print(f"Found {len(qa_procedures)} QA procedures")

    # Search by keyword
    review_procedures = proc_mem.search_by_keyword("review")
    print(f"Found {len(review_procedures)} review procedures")

    # Retrieve for agent context
    context = proc_mem.retrieve_for_context(
        keywords=["code", "review"],
        tags=["sop"],
        max_entries=3,
    )
    print(f"Agent context:\n{context}")


# =============================================================================
# Example 2: Memory Consolidation — Episodic to Semantic
# =============================================================================

def example_memory_consolidation():
    """Consolidate episodic memory into semantic memory."""

    store = MemoryStore()

    # Simulate episodic memory accumulation
    for i in range(15):
        store.submit_candidate(
            agent_id="dev_agent",
            layer="episodic",
            domain="sprint_events",
            content=f"Sprint {i}: Completed feature X with 85% test coverage",
        )

    # Review and store candidates
    store.review_pending(auto_store=True)

    # Check if consolidation is needed
    if store.check_consolidation_needed():
        print("Consolidation recommended")

        # Consolidate episodic → semantic (without LLM)
        semantic_entries = store.consolidate_episodic_to_semantic(
            agent_id="system",
            use_llm=False,  # Set to True to use LLM-powered consolidation
        )

        print(f"Created {len(semantic_entries)} semantic entries")
        for entry in semantic_entries:
            print(f"  - [{entry.domain}] {entry.content[:100]}")


# =============================================================================
# Example 3: Dual Retrieval Strategy — RAG + SQL
# =============================================================================

def example_dual_retrieval():
    """Demonstrate hybrid retrieval: RAG for semantic, SQL for episodic."""

    store = MemoryStore()

    # Seed semantic memory (facts, patterns)
    store.seed_from_dict("semantic", "coding_standards", {
        "key": "error_handling",
        "value": "Always use explicit error handling, never swallow exceptions",
        "classification": "internal",
    })

    # Seed episodic memory (time-series events)
    store.seed_from_dict("episodic", "deploy_events", [
        {"content": "2026-07-01T10:00:00: Deployed v1.2.0 to production"},
        {"content": "2026-07-01T14:30:00: Rollback due to memory leak"},
        {"content": "2026-07-02T09:00:00: Fixed memory leak, deployed v1.2.1"},
    ])

    # Hybrid retrieval: semantic search + time-series query
    results = store.retrieve_hybrid(
        agent_id="ceo",
        query="error handling deployment",
        start_date="2026-07-01T00:00:00",
        end_date="2026-07-02T23:59:59",
        max_entries=10,
    )

    print("Hybrid retrieval results:")
    print(f"  Semantic: {len(results['semantic'])} entries")
    print(f"  Episodic: {len(results['episodic'])} entries")
    print(f"  Long-term: {len(results['long_term'])} entries")

    # Time-series query for episodic memory
    recent_deploys = store.search_episodic_by_time(
        agent_id="ceo",
        start_date="2026-07-01T00:00:00",
        domain="deploy_events",
    )

    print(f"\nRecent deploys: {len(recent_deploys)}")
    for deploy in recent_deploys:
        print(f"  - {deploy.content}")


# =============================================================================
# Example 4: Memory Health Metrics
# =============================================================================

def example_memory_health():
    """Get memory health metrics and diagnostics."""

    store = MemoryStore()

    # Seed some data
    for i in range(120):
        store.submit_candidate(
            agent_id="agent",
            layer="episodic",
            domain="events",
            content=f"Event {i}",
        )

    store.review_pending(auto_store=True)

    # Get health metrics
    metrics = store.get_memory_health_metrics()

    print("Memory Health Metrics:")
    print(f"  Timestamp: {metrics['timestamp']}")
    print(f"  Consolidation needed: {metrics['consolidation_needed']}")
    print(f"  Last consolidation: {metrics['last_consolidation']}")

    for layer, stats in metrics['layers'].items():
        print(f"\n  {layer.upper()}:")
        print(f"    Domains: {stats['domains']}")
        print(f"    Active entries: {stats['active_entries']}")
        print(f"    Superseded entries: {stats['superseded_entries']}")

    print(f"\n  PROCEDURAL:")
    print(f"    Total procedures: {metrics['procedural']['total_procedures']}")
    print(f"    Average usage: {metrics['procedural']['avg_usage']:.2f}")


# =============================================================================
# Example 5: Complete Workflow
# =============================================================================

def example_complete_workflow():
    """Complete workflow: procedural + consolidation + hybrid retrieval."""

    # Initialize memory store with procedural memory
    store = MemoryStore()

    # Load SOPs
    sop_dir = Path("./sops")
    if sop_dir.exists():
        count = store.procedural.load_from_directory(sop_dir)
        print(f"Loaded {count} SOPs")

    # Add procedural memory for agent context
    store.procedural.add_procedure(
        name="sprint_planning",
        description="How to plan a sprint",
        content="1. Review backlog\n2. Estimate stories\n3. Commit to sprint goal",
        tags=["planning", "agile"],
    )

    # Accumulate episodic memory
    for i in range(50):
        store.submit_candidate(
            agent_id="pm_agent",
            layer="episodic",
            domain="sprint_events",
            content=f"Sprint {i}: Velocity {30 + i % 10} points",
        )

    store.review_pending(auto_store=True)

    # Auto-consolidate if needed
    if store.check_consolidation_needed():
        print("Auto-consolidating episodic → semantic")
        semantic = store.consolidate_episodic_to_semantic(use_llm=False)
        print(f"Created {len(semantic)} semantic patterns")

    # Retrieve for agent with hybrid strategy
    context = store.retrieve_hybrid(
        agent_id="pm_agent",
        query="sprint velocity planning",
        max_entries=5,
    )

    print("\nHybrid context for PM agent:")
    for layer, entries in context.items():
        if entries:
            print(f"  {layer}: {len(entries)} entries")

    # Get procedural context
    proc_context = store.procedural.retrieve_for_context(
        keywords=["sprint", "planning"],
        max_entries=2,
    )
    print(f"\nProcedural context:\n{proc_context[:200]}...")

    # Health check
    print(f"\n{store.summary()}")


if __name__ == "__main__":
    print("=" * 70)
    print("TAZ OS Enhanced Memory System — Usage Examples")
    print("=" * 70)

    print("\n[1] Procedural Memory")
    print("-" * 70)
    example_procedural_memory()

    print("\n[2] Memory Consolidation")
    print("-" * 70)
    example_memory_consolidation()

    print("\n[3] Dual Retrieval Strategy")
    print("-" * 70)
    example_dual_retrieval()

    print("\n[4] Memory Health Metrics")
    print("-" * 70)
    example_memory_health()

    print("\n[5] Complete Workflow")
    print("-" * 70)
    example_complete_workflow()
