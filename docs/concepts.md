# Concepts

## The central rule

Raw evidence and canonical records are permanent. Dashboards, indexes, daily summaries, and weekly plans are derived views.

This prevents a polished summary from becoming the only surviving account of what happened.

## Evidence is not the same as truth

A meeting transcript proves that a statement was made. A test result proves what that test observed under its recorded conditions. An agent conclusion is an inference until suitable evidence verifies it.

Daily Context preserves those differences through record kinds, evidence status, stable IDs, and source links.

## Current state and history

Chronological day folders provide the audit trail. The `registry/` files and `CONTEXT.md` provide the current projection. This avoids copying the same open task or decision through many daily files.

## Corrections

Corrections add a new linked record. Raw evidence is not rewritten, and a superseded decision remains available with a link to its replacement.

## Why search is secondary

Each root, day, and week has a bounded index. Stable IDs make direct lookup and trace-back predictable. Semantic search can help discovery later, but it is not the source of truth.

## Standards behind the design

The provenance model borrows the useful core of W3C PROV: entities, activities, agents, usage, generation, and derivation. Decision records borrow the immutable-successor pattern used by architecture decision records. The repository does not claim formal conformance to either standard.
