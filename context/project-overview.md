# Project Overview

## Product

EAICS is a synthetic-data enterprise customer service and complaint-resolution platform for a retail financial-services scenario. It combines customer conversations, AI-assisted service, human operations, complaint handling, policy-controlled tools, knowledge retrieval, quality review, and management reporting. The FRD and TRD PDFs are the source of truth; their canonical approved versions must be confirmed because the FRD cover is v0.9 draft while the TRD references FRD v1.0.

## Problem and goals

The product aims to maintain context across service channels, resolve suitable requests safely with AI assistance, route uncertain or sensitive requests to people, track complaints and service commitments, and provide auditable operational outcomes. Customer and staff experiences are equal product surfaces.

## Personas and roles

Roles found in `app/core/rbac.py`: customer, AI agent, customer service agent, supervisor, complaint officer, QA analyst, administrator, and management. Detailed route/action/data permissions must be traceable to FRD §4.2 and enforced using a verified principal. Current `X-Role` selection is a prototype mechanism, not authentication.

## Core journeys

1. Customer identifies/authenticates to the level required for an action, chats or submits a service request, receives grounded information or a safe handoff, tracks owned cases, and gives feedback.
2. AI classifies intent/context/risk, retrieves relevant knowledge, applies policy to registered tools, records outcomes, and hands off when required.
3. Agent accepts prioritized work, reviews verified customer context and clearly labeled AI assistance, responds or transfers, and resolves supported work.
4. Supervisor/complaint officer monitors SLA/escalations, reviews cases and approvals, and records authorized decisions.
5. Knowledge manager maintains source/version/review state and validates retrieval; QA reviews evidence against approved criteria; management reads explainable metrics; administrator manages authorized configuration and audit.

These journeys summarize the supplied product prompt and repository modules; exact acceptance rules must be checked in the FRD/TRD before implementation.

## Feature categories

- Customer portal, authentication, conversations, channel simulators, complaint submission, ticket/case tracking, feedback.
- AI orchestration, intent/context/sentiment, policy, tool registry/gateway, handoff, knowledge/RAG/citations.
- Agent queue/workspace, supervisor and complaint workflows, SLA/escalation, approvals.
- Knowledge lifecycle, QA sampling/evaluation, root-cause analytics, management reporting.
- RBAC, tenant/customer scoping, audit trail, integrations and operational reliability.

## Scope

In scope: preserve and incrementally complete the existing FastAPI/React modular monolith and its documented synthetic banking workflows; add role-suitable interfaces and backend-enforced authorization as requirements permit.

Out of scope unless FRD/TRD explicitly requires and providers are approved: production financial transactions, use of real customer data, unapproved external LLM/CRM/channel providers, replacement of the current stack, and claims of production-grade model or RAG behavior from simulator implementations.

## Observable success criteria

- Every implemented role route maps to an approved permission; backend tests prove denied roles cannot perform actions or read another customer's/tenant's records.
- A customer can complete the documented sign-in, conversation, complaint, tracking, handoff, and feedback journeys using persisted API data and receives understandable validation/error/success feedback.
- Agents can accept and manage a handoff and see conversation context, linked objects, SLA, and AI-generated content with provenance.
- Supervisor/complaint, knowledge, QA, management, and admin screens expose only their approved actions and derive displayed data from documented sources.
- Every visible control has a working behavior or an explained disabled/prototype state; pages support keyboard focus and responsive desktop/tablet/mobile layouts.
- Existing documented business invariants remain covered by regression verification; no stub is represented as a successful real external operation.
- Build and verification results are recorded per unit, with actual command outcomes.

## Non-functional criteria

Follow FRD/TRD for security, privacy, auditability, availability, latency, accessibility, and retention targets. Until exact targets are traced, preserve deny-by-default authorization, minimum data access, correlated audit, safe error handling, responsive layouts, and explicit synthetic-data labeling. Numerical service targets remain open until verified from the requirements.
