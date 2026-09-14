# Phase Commit Reviewer

A read-only companion Agent Skill for `parallel-plan-implementation`.

It reviews one phase commit using its exact diff plus approved delivery scope, preserved-behavior obligations, plan, boundary, contract, repository, and final-state context. It returns up to 15 verified findings in a deterministic JSON shape and never edits code or history.

Requested runtime profile:

- model: `gpt-5.6-sol`;
- reasoning effort: `xhigh`;
- one fresh isolated agent per phase commit.

The main orchestrator remains responsible for verifying findings, assigning the earliest responsible phase, adding fixes and regression tests, reconstructing descendant history, and restoring a fully passing repository.

## Embedded complete-description comment

The source `SKILL.md` begins with a `COMPLETE SKILL DESCRIPTION` HTML comment covering its exact single-commit scope, required phase context, review angles, structured output, and strict read-only boundary. The shorter YAML `description` remains optimized for skill discovery and activation.
