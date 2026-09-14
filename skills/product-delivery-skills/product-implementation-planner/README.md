# Product Implementation Planner

An Agent Skill that turns a product idea or a change to an existing repository into a production-grade architecture and phased implementation plan complete for the approved scope under `docs/implementation-plan/`. It supports full products, scoped features, modernization or migration, and remediation or reliability work, selecting decomposition from domain, repository, language, state, and operational evidence instead of imposing one universal programming or architecture style.

## Embedded complete-description comment

The source `SKILL.md` begins with a `COMPLETE SKILL DESCRIPTION` HTML comment that explains the full intake, clarification, architecture-planning, validation, approval, and implementation-handoff lifecycle. The shorter YAML `description` remains optimized for skill discovery and activation.

## Workflow

1. Obtain or normalize the product or change description and record one canonical typed delivery-scope block.
2. Ask a tailored set of principal architecture questions, including hosting/operating model when unresolved.
3. Classify unknowns as blocking, decision-gated, or non-blocking.
4. Establish the impact cone, select decomposition independently across domain, dependency, state, organization, deployment, and programming-model axes, and test candidates against representative changes.
5. Produce or update the applicable product, architecture, data, interface, security, operations, testing, delivery, and component plans with stable identifiers.
6. Create a concise derived `delivery-status.md` for human observers, with links to the detailed evidence.
7. Validate subsystem classifications, data writers, dependency types, write domains, shared-state constraints, and candidate parallel waves.
8. Tell the operator that the status summary was updated, then ask whether implementation should proceed with `parallel-plan-implementation`.

The planner remains planning-only until the user explicitly approves implementation.

## Delivery companions

- `parallel-plan-implementation` executes the validated plan with contract-first boundaries, isolated worktrees, and one traceable commit per phase.
- `phase-commit-reviewer` powers the optional fresh-agent review of each phase commit after implementation is fully integrated, buildable, and passing.

Implementation and review have separate approval gates. Approving implementation does not automatically authorize reviewer dispatch, fixes, or history reconstruction.

## Requested delivery profiles

- Main agent: `gpt-5.6-sol` / `ultra`
- Implementor agents: `gpt-5.6-terra` / `xhigh`
- Reviewer agents: `gpt-5.6-sol` / `xhigh`

The host controls model availability. Requested and actual profiles are recorded, and substitutions require explicit user approval.

## Validation

```bash
python3 <skill-root>/scripts/validate_plan.py <repository-root>
```

For a deliberately selected non-default planning root, add `--plan-root <plan-root>`; relative values resolve from the repository root.

The validator checks scope-appropriate documents and sections, the human delivery-status structure, date format, and agreement with planning readiness, stable identifiers, decomposition scenarios and alternatives, subsystem classifications, data writers, component phases, dependency classifications, traceability, decision gates, boundary candidates, write domains, and preliminary parallel waves.
